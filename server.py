import json
import re
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urljoin, urlparse

import chromadb
import chromadb.utils.embedding_functions as ef
import httpx
import tiktoken
from bs4 import BeautifulSoup
from markdownify import markdownify
from mcp.server.fastmcp import Context, FastMCP

enc = tiktoken.get_encoding("cl100k_base")

CHROMA_PATH = Path(__file__).parent / "data" / "chroma"
VALID_NAME = re.compile(r"^[a-zA-Z0-9_-]{3,63}$")

embed_fn = ef.DefaultEmbeddingFunction()

_chroma_client: chromadb.api.ClientAPI | None = None
_current_collection: chromadb.Collection | None = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    global _chroma_client
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    yield {}


mcp = FastMCP("scraper", lifespan=lifespan)


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["footer", "header"]):
        tag.decompose()
    base = urlparse(base_url)
    links = []
    for tag in soup.find_all("a", href=True):
        url = urljoin(base_url, tag["href"]).split("#")[0]
        parsed = urlparse(url)
        if parsed.netloc == base.netloc and parsed.scheme in ("http", "https"):
            links.append(url)
    return list(dict.fromkeys(links))


def parse(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["nav", "footer", "script", "style", "header"]):
        tag.decompose()
    return markdownify(str(soup.body), heading_style="ATX")


def chunk(text: str, max_tokens: int = 500) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current, count = [], [], 0
    for para in paragraphs:
        n = len(enc.encode(para))
        if count + n > max_tokens and current:
            chunks.append("\n\n".join(current))
            current, count = [], 0
        current.append(para)
        count += n
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _openapi_documents(spec: dict, url: str) -> tuple[list[str], list[str], list[dict]]:
    info = spec.get("info", {})
    base_title = info.get("title", "")
    documents, ids, metadatas = [], [], []
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = operation.get("operationId", f"{method}_{path}")
            summary = operation.get("summary", "")
            description = operation.get("description", "")
            tags = ", ".join(operation.get("tags", []))
            params = [
                f"- {p.get('name')} ({p.get('in')}): {p.get('description', '')}"
                for p in operation.get("parameters", [])
            ]
            params_text = "\n".join(params) if params else ""
            text = "\n".join(filter(None, [
                f"# {method.upper()} {path}",
                f"**API:** {base_title}",
                f"**Tags:** {tags}" if tags else None,
                f"**Summary:** {summary}" if summary else None,
                description if description else None,
                f"**Parameters:**\n{params_text}" if params_text else None,
            ]))
            documents.append(text)
            ids.append(f"{url}::{op_id}")
            metadatas.append({"source_url": url, "path": path, "method": method})
    return documents, ids, metadatas


async def _resolve_swagger_spec_urls(swagger_ui_url: str) -> list[str]:
    base = swagger_ui_url.rsplit("/", 1)[0]
    parsed = urlparse(swagger_ui_url)
    api_base = f"{parsed.scheme}://{parsed.netloc}"

    response = await _fetch(f"{base}/swagger-initializer.js")
    if response:
        match = re.search(r'url:\s*["\']([^"\']+)["\']', response.text)
        if match:
            spec_url = urljoin(api_base, match.group(1))
            if "petstore" not in spec_url:
                return [spec_url]

    response = await _fetch(f"{base}/index.js")
    if response:
        match = re.search(r"JSON\.parse\('(.+?)'\)", response.text)
        if match:
            try:
                config = json.loads(match.group(1))
                urls = config.get("urls", [])
                return [urljoin(api_base, u["url"]) for u in urls if "url" in u]
            except Exception:
                pass

    return []


def _extract_swagger_ui_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = []
    for tag in soup.find_all("a", href=True):
        url = urljoin(base_url, tag["href"]).split("#")[0]
        if re.search(r"/swagger/index\.html$", url):
            links.append(url)
    return list(dict.fromkeys(links))


def _is_openapi(response: httpx.Response) -> bool:
    ct = response.headers.get("content-type", "")
    if "json" not in ct:
        return False
    try:
        spec = response.json()
        return "paths" in spec and ("openapi" in spec or "swagger" in spec)
    except Exception:
        return False


async def _fetch(url: str) -> httpx.Response | None:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response
    except Exception:
        return None


def _is_indexed(collection: chromadb.Collection, url: str) -> bool:
    return bool(collection.get(where={"source_url": url})["ids"])


def _upsert(
    collection: chromadb.Collection,
    documents: list[str],
    ids: list[str],
    metadatas: list[dict],
    url: str,
) -> bool:
    if not documents:
        return False
    existing = collection.get(where={"source_url": url})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
    collection.add(documents=documents, ids=ids, metadatas=metadatas)
    return True


async def _index_response(
    collection: chromadb.Collection, url: str, response: httpx.Response
) -> tuple[bool, bool, list[str]]:
    if _is_openapi(response):
        docs, ids, metas = _openapi_documents(response.json(), url)
        return _upsert(collection, docs, ids, metas, url), True, []
    html = response.text
    swagger_spec_urls = []
    for swagger_ui_url in _extract_swagger_ui_links(html, url):
        for spec_url in await _resolve_swagger_spec_urls(swagger_ui_url):
            spec_response = await _fetch(spec_url)
            if spec_response and _is_openapi(spec_response):
                docs, ids, metas = _openapi_documents(spec_response.json(), spec_url)
                _upsert(collection, docs, ids, metas, spec_url)
                swagger_spec_urls.append(spec_url)
    chunks = chunk(parse(html))
    ids = [f"{url}::{i}" for i in range(len(chunks))]
    metas = [{"source_url": url} for _ in chunks]
    return _upsert(collection, chunks, ids, metas, url), False, swagger_spec_urls


def _enqueue_links(html: str, base_url: str, depth: int, visited: set, queue: deque) -> None:
    for link in extract_links(html, base_url):
        if link not in visited:
            queue.append((link, depth + 1))


def _create_namespace(client: chromadb.api.ClientAPI, name: str) -> str:
    if not VALID_NAME.match(name):
        return f"Invalid name '{name}'. Use 3-63 chars, alphanumeric + hyphens/underscores only."
    client.get_or_create_collection(name, embedding_function=embed_fn)
    return f"Namespace '{name}' ready."


def _use_namespace(client: chromadb.api.ClientAPI, name: str) -> str:
    global _current_collection
    try:
        _current_collection = client.get_collection(name, embedding_function=embed_fn)
        return f"Using namespace '{name}'."
    except Exception:
        return f"Namespace '{name}' does not exist. Call create_namespace('{name}') first."


def _delete_namespace(client: chromadb.api.ClientAPI, name: str) -> str:
    global _current_collection
    try:
        client.delete_collection(name)
    except Exception:
        return f"Namespace '{name}' does not exist."
    if _current_collection is not None and _current_collection.name == name:
        _current_collection = None
    return f"Namespace '{name}' deleted."


def _list_namespaces(client: chromadb.api.ClientAPI) -> list[str]:
    return [c.name for c in client.list_collections()]


def _current_namespace() -> str:
    if _current_collection is None:
        return "No namespace selected."
    return _current_collection.name


@mcp.tool()
def create_namespace(name: str) -> str:
    """Create a new namespace. Does not switch to it."""
    return _create_namespace(_chroma_client, name)


@mcp.tool()
def use_namespace(name: str) -> str:
    """Set the active namespace for this session."""
    return _use_namespace(_chroma_client, name)


@mcp.tool()
def delete_namespace(name: str) -> str:
    """Delete a namespace and all its indexed data."""
    return _delete_namespace(_chroma_client, name)


@mcp.tool()
def list_namespaces() -> list[str]:
    """List all existing namespaces."""
    return _list_namespaces(_chroma_client)


@mcp.tool()
def current_namespace() -> str:
    """Return the active namespace name, or a message if none is set."""
    return _current_namespace()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
