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
VALID_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,61}[a-zA-Z0-9]$")

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


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
def create_namespace(name: str) -> str:
    """Create a new namespace and switch to it immediately."""
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


@mcp.tool()
async def index_page(url: str) -> str:
    """Fetch a documentation page and add it to the current namespace index."""
    return await _index_page_tool(url)


@mcp.tool()
async def index_tree(url: str, ctx: Context, max_depth: int = 2, force: bool = False) -> str:
    """Fetch a documentation site and recursively index all pages on the same domain."""
    return await _index_tree_tool(url, max_depth, force, ctx.info)


@mcp.tool()
async def discover_links(url: str, max_depth: int = 2) -> list[str]:
    """Discover all pages reachable from a URL within max_depth hops on the same domain."""
    return await _discover_links(url, max_depth)


@mcp.tool()
def list_indexed_pages() -> list[dict]:
    """List all pages currently in the active namespace index."""
    if _current_collection is None:
        return []
    return _list_indexed_pages(_current_collection)


@mcp.tool()
def clear_index() -> str:
    """Delete all documents from the active namespace index."""
    if _current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    return _clear_index(_current_collection)


@mcp.tool()
def search_docs(query: str, n_results: int = 5) -> dict:
    """Search the active namespace. Returns relevant chunks with source URLs and a deduplicated references list."""
    return _search_docs_tool(query, n_results)


# ---------------------------------------------------------------------------
# Namespace management
# ---------------------------------------------------------------------------


def _create_namespace(client: chromadb.api.ClientAPI, name: str) -> str:
    global _current_collection
    if not VALID_NAME.match(name):
        return f"Invalid name '{name}'. Use 3-63 chars, alphanumeric + hyphens/underscores only."
    _current_collection = client.get_or_create_collection(name, embedding_function=embed_fn)
    return f"Namespace '{name}' created and is now active."


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


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


async def _index_page_tool(url: str) -> str:
    if _current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    return await _index_page(_current_collection, url)


async def _index_page(collection: chromadb.Collection, url: str) -> str:
    response = await _fetch(url)
    if response is None:
        return f"Failed to fetch {url}"
    indexed, is_openapi, swagger_specs = await _index_response(collection, url, response)
    if not indexed:
        return f"No content extracted from {url}"
    kind = "operations" if is_openapi else "chunks"
    count = len(collection.get(where={"source_url": url})["ids"])
    msg = f"Indexed {count} {kind} from {url}"
    for spec_url in swagger_specs:
        op_count = len(collection.get(where={"source_url": spec_url})["ids"])
        msg += f"\n  + {op_count} operations from {spec_url}"
    return msg


async def _index_tree_tool(url: str, max_depth: int = 2, force: bool = False, log=None) -> str:
    if _current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    return await _index_tree(_current_collection, url, max_depth, force, log)


async def _index_tree(
    collection: chromadb.Collection,
    url: str,
    max_depth: int = 2,
    force: bool = False,
    log=None,
) -> str:
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(url, 0)])
    indexed, skipped, failed = 0, 0, 0

    while queue:
        current_url, depth = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        if not force and _is_indexed(collection, current_url):
            skipped += 1
            if log:
                await log(f"[skipped] {current_url}")
            response = await _fetch(current_url)
            if response and depth < max_depth and "json" not in response.headers.get("content-type", ""):
                _enqueue_links(response.text, current_url, depth, visited, queue)
            continue

        response = await _fetch(current_url)
        if response is None:
            failed += 1
            continue

        try:
            ok, is_openapi, _ = await _index_response(collection, current_url, response)
        except Exception:
            failed += 1
            continue

        if ok:
            indexed += 1

        if depth < max_depth and not is_openapi:
            _enqueue_links(response.text, current_url, depth, visited, queue)

    return f"Indexed {indexed} pages ({skipped} skipped, {failed} failed) starting from {url}"


def _list_indexed_pages(collection: chromadb.Collection) -> list[dict]:
    if collection.count() == 0:
        return []
    metadatas = collection.get()["metadatas"]
    counts: dict[str, int] = {}
    for meta in metadatas:
        url = meta.get("source_url", "unknown")
        counts[url] = counts.get(url, 0) + 1
    return [{"url": url, "chunks": n} for url, n in sorted(counts.items())]


def _clear_index(collection: chromadb.Collection) -> str:
    count = collection.count()
    if count == 0:
        return "Index already empty."
    all_ids = collection.get()["ids"]
    collection.delete(ids=all_ids)
    return f"Deleted {count} documents from index."


def _search_docs_tool(query: str, n_results: int = 5) -> dict:
    if _current_collection is None:
        return {"error": "No namespace selected. Call use_namespace(name) first."}
    if _current_collection.count() == 0:
        return {"error": "Namespace is empty. Call index_page(url) first."}
    return _search_docs(_current_collection, query, n_results)


def _search_docs(collection: chromadb.Collection, query: str, n_results: int = 5) -> dict:
    effective = min(max(n_results, 1), collection.count())
    if effective == 0:
        return {"results": [], "references": []}
    results = collection.query(query_texts=[query], n_results=effective)
    output = []
    seen_urls: list[str] = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        url = meta.get("source_url", "unknown")
        output.append({
            "text": doc,
            "source_url": url,
            "relevance_score": round(max(0.0, 1 - dist), 3),
        })
        if url not in seen_urls:
            seen_urls.append(url)
    return {"results": output, "references": seen_urls}


# ---------------------------------------------------------------------------
# Crawling helpers
# ---------------------------------------------------------------------------


async def _discover_links(url: str, max_depth: int = 2) -> list[str]:
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(url, 0)])
    found: list[str] = []

    while queue:
        current_url, depth = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)
        found.append(current_url)

        if depth < max_depth:
            response = await _fetch(current_url)
            if response and "json" not in response.headers.get("content-type", ""):
                _enqueue_links(response.text, current_url, depth, visited, queue)

    return found


def _enqueue_links(html: str, base_url: str, depth: int, visited: set, queue: deque) -> None:
    for link in extract_links(html, base_url):
        if link not in visited:
            queue.append((link, depth + 1))


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


# ---------------------------------------------------------------------------
# HTTP & parsing
# ---------------------------------------------------------------------------


async def _fetch(url: str) -> httpx.Response | None:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response
    except Exception:
        return None


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


# ---------------------------------------------------------------------------
# OpenAPI / Swagger helpers
# ---------------------------------------------------------------------------


def _is_openapi(response: httpx.Response) -> bool:
    ct = response.headers.get("content-type", "")
    if "json" not in ct:
        return False
    try:
        spec = response.json()
        return "paths" in spec and ("openapi" in spec or "swagger" in spec)
    except Exception:
        return False


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
                if _upsert(collection, docs, ids, metas, spec_url):
                    swagger_spec_urls.append(spec_url)
    chunks = chunk(parse(html))
    ids = [f"{url}::{i}" for i in range(len(chunks))]
    metas = [{"source_url": url} for _ in chunks]
    return _upsert(collection, chunks, ids, metas, url), False, swagger_spec_urls


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


def _openapi_documents(spec: dict, url: str) -> tuple[list[str], list[str], list[dict]]:
    info = spec.get("info", {})
    base_title = info.get("title", "")
    components = spec.get("components", {})
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

            request_body = operation.get("requestBody", {})
            request_text = _extract_schema_text(request_body.get("content", {}), components)

            response_text = ""
            for code, response in operation.get("responses", {}).items():
                if str(code).startswith("2"):
                    response_text = _extract_schema_text(response.get("content", {}), components)
                    break

            text = "\n".join(filter(None, [
                f"# {method.upper()} {path}",
                f"**API:** {base_title}",
                f"**Tags:** {tags}" if tags else None,
                f"**Summary:** {summary}" if summary else None,
                description if description else None,
                f"**Parameters:**\n{params_text}" if params_text else None,
                f"**Request Body:**\n{request_text}" if request_text else None,
                f"**Response:**\n{response_text}" if response_text else None,
            ]))
            documents.append(text)
            ids.append(f"{url}::{op_id}")
            metadatas.append({"source_url": url, "path": path, "method": method})
    return documents, ids, metadatas


def _resolve_ref(schema: dict, components: dict) -> dict:
    ref = schema.get("$ref", "")
    if not ref.startswith("#/components/schemas/"):
        return schema
    name = ref.split("/")[-1]
    return components.get("schemas", {}).get(name, schema)


def _schema_to_text(schema: dict, components: dict, depth: int = 0, visited: frozenset = frozenset()) -> str:
    if depth > 4:
        return ""
    schema = _resolve_ref(schema, components)
    ref_key = schema.get("$ref", id(schema))
    if ref_key in visited:
        return ""
    visited = visited | {ref_key}

    lines = []
    indent = "  " * depth

    for sub in schema.get("allOf", []) + schema.get("anyOf", []) + schema.get("oneOf", []):
        lines.append(_schema_to_text(_resolve_ref(sub, components), components, depth, visited))

    if "properties" in schema or schema.get("type") == "object":
        required_fields = set(schema.get("required", []))
        for name, prop in schema.get("properties", {}).items():
            prop = _resolve_ref(prop, components)
            prop_type = prop.get("type", "object" if "properties" in prop else "")
            if prop_type == "array" and "items" in prop:
                prop_type = f"array[{_resolve_ref(prop['items'], components).get('type', 'object')}]"
            req = "*" if name in required_fields else ""
            desc = prop.get("description", "")
            line = f"{indent}- {name}{req} ({prop_type})"
            if desc:
                line += f": {desc}"
            lines.append(line)
            if "properties" in prop or "allOf" in prop or "anyOf" in prop or "oneOf" in prop:
                lines.append(_schema_to_text(prop, components, depth + 1, visited))
    elif schema.get("type") == "array" and "items" in schema:
        lines.append(_schema_to_text(_resolve_ref(schema["items"], components), components, depth, visited))

    return "\n".join(filter(None, lines))


def _extract_schema_text(content: dict, components: dict) -> str:
    for media_content in content.values():
        schema = media_content.get("schema", {})
        if schema:
            return _schema_to_text(schema, components)
    return ""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

import asyncio
import os

import uvicorn


async def _run_all() -> None:
    from router import app as http_app
    port = int(os.environ.get("HTTP_PORT", "8000"))
    config = uvicorn.Config(http_app, host="0.0.0.0", port=port, log_level="info")
    http_server = uvicorn.Server(config)
    await asyncio.gather(
        mcp.run_async(transport="stdio"),
        http_server.serve(),
    )


def main() -> None:
    asyncio.run(_run_all())


if __name__ == "__main__":
    main()
