# Scraper MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone MCP server that scrapes and indexes web pages/OpenAPI specs into isolated, named namespaces using ChromaDB, with semantic search scoped per namespace.

**Architecture:** Single FastMCP server with module-level globals `_chroma_client` and `_current_collection` for session state. Business logic in private `_impl` functions (testable); MCP tools are thin wrappers. One ChromaDB collection per namespace inside a shared `PersistentClient`.

**Tech Stack:** FastMCP, ChromaDB, httpx, BeautifulSoup, markdownify, tiktoken, pytest, pytest-asyncio

---

## File Structure

| File | Responsibility |
|------|---------------|
| `scraper/pyproject.toml` | deps, pytest config |
| `scraper/server.py` | module state, all impl functions, all MCP tool wrappers |
| `scraper/tests/__init__.py` | empty, marks tests as package |
| `scraper/tests/conftest.py` | autouse fixture: ephemeral ChromaDB + state reset |
| `scraper/tests/test_namespaces.py` | namespace tools + helper smoke tests |
| `scraper/tests/test_indexing.py` | index_page, index_tree, discover_links |
| `scraper/tests/test_search.py` | list_indexed_pages, clear_index, search_docs |

---

### Task 1: Project scaffold

**Files:**
- Create: `scraper/pyproject.toml`
- Create: `scraper/server.py`
- Create: `scraper/tests/__init__.py`
- Create: `scraper/tests/conftest.py`

- [ ] **Step 1: Create `scraper/pyproject.toml`**

```toml
[project]
name = "scraper-mcp"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "beautifulsoup4>=4.14.3",
    "chromadb>=1.5.9",
    "httpx>=0.28.1",
    "lxml>=6.1.1",
    "markdownify>=1.2.2",
    "mcp[cli]>=1.27.1",
    "tiktoken>=0.13.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[tool.pytest.ini_options]
pythonpath = ["."]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create `scraper/server.py`**

```python
import re
from contextlib import asynccontextmanager
from pathlib import Path

import chromadb
import chromadb.utils.embedding_functions as ef
from mcp.server.fastmcp import FastMCP

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


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create `scraper/tests/__init__.py`** (empty file)

- [ ] **Step 4: Create `scraper/tests/conftest.py`**

```python
import chromadb
import pytest
import server


@pytest.fixture(autouse=True)
def reset_state():
    server._chroma_client = chromadb.EphemeralClient()
    server._current_collection = None
    yield
    server._chroma_client = None
    server._current_collection = None
```

- [ ] **Step 5: Install deps and verify import**

```bash
cd scraper
uv sync
uv run python -c "import server; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add scraper/
git commit -m "feat(scraper): scaffold project structure"
```

---

### Task 2: Namespace management tools

**Files:**
- Modify: `scraper/server.py`
- Create: `scraper/tests/test_namespaces.py`

- [ ] **Step 1: Write failing tests in `scraper/tests/test_namespaces.py`**

```python
import server


def test_create_namespace_valid():
    result = server._create_namespace(server._chroma_client, "my-ns")
    assert result == "Namespace 'my-ns' ready."


def test_create_namespace_idempotent():
    server._create_namespace(server._chroma_client, "my-ns")
    result = server._create_namespace(server._chroma_client, "my-ns")
    assert result == "Namespace 'my-ns' ready."


def test_create_namespace_invalid_name():
    result = server._create_namespace(server._chroma_client, "a")
    assert "Invalid name" in result


def test_list_namespaces_empty():
    assert server._list_namespaces(server._chroma_client) == []


def test_list_namespaces():
    server._create_namespace(server._chroma_client, "ns-one")
    server._create_namespace(server._chroma_client, "ns-two")
    names = server._list_namespaces(server._chroma_client)
    assert set(names) == {"ns-one", "ns-two"}


def test_use_namespace():
    server._create_namespace(server._chroma_client, "my-ns")
    result = server._use_namespace(server._chroma_client, "my-ns")
    assert result == "Using namespace 'my-ns'."
    assert server._current_collection is not None
    assert server._current_collection.name == "my-ns"


def test_use_namespace_nonexistent():
    result = server._use_namespace(server._chroma_client, "ghost")
    assert "does not exist" in result
    assert server._current_collection is None


def test_current_namespace_none():
    assert server._current_namespace() == "No namespace selected."


def test_current_namespace_set():
    server._create_namespace(server._chroma_client, "my-ns")
    server._use_namespace(server._chroma_client, "my-ns")
    assert server._current_namespace() == "my-ns"


def test_delete_namespace():
    server._create_namespace(server._chroma_client, "my-ns")
    result = server._delete_namespace(server._chroma_client, "my-ns")
    assert result == "Namespace 'my-ns' deleted."
    assert "my-ns" not in server._list_namespaces(server._chroma_client)


def test_delete_namespace_clears_current():
    server._create_namespace(server._chroma_client, "my-ns")
    server._use_namespace(server._chroma_client, "my-ns")
    server._delete_namespace(server._chroma_client, "my-ns")
    assert server._current_collection is None


def test_delete_namespace_nonexistent():
    result = server._delete_namespace(server._chroma_client, "ghost")
    assert "does not exist" in result
```

- [ ] **Step 2: Run to verify failure**

```bash
cd scraper
uv run pytest tests/test_namespaces.py -v
```
Expected: `AttributeError: module 'server' has no attribute '_create_namespace'`

- [ ] **Step 3: Add impl functions to `scraper/server.py` (before `main`)**

```python
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
```

- [ ] **Step 4: Add MCP tool wrappers to `scraper/server.py` (after impl functions)**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd scraper
uv run pytest tests/test_namespaces.py -v
```
Expected: All 11 tests pass.

- [ ] **Step 6: Commit**

```bash
git add scraper/server.py scraper/tests/test_namespaces.py
git commit -m "feat(scraper): add namespace management tools"
```

---

### Task 3: Helper utilities

**Files:**
- Modify: `scraper/server.py`
- Modify: `scraper/tests/test_namespaces.py`

These are copied verbatim from `../server.py`. A quick smoke test confirms the copy is intact.

- [ ] **Step 1: Add imports to top of `scraper/server.py`**

Add after the existing imports:

```python
import json
from collections import deque
from urllib.parse import urljoin, urlparse

import httpx
import tiktoken
from bs4 import BeautifulSoup
from markdownify import markdownify
from mcp.server.fastmcp import Context

enc = tiktoken.get_encoding("cl100k_base")
```

- [ ] **Step 2: Add helper functions to `scraper/server.py` (before `_create_namespace`)**

Copy these verbatim from `../server.py`:

```python
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
        return "paths" in spec and "openapi" in spec or "swagger" in spec
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
```

- [ ] **Step 3: Add smoke tests to `scraper/tests/test_namespaces.py`**

```python
from server import chunk, parse


def test_chunk_splits_large_text():
    big = "\n\n".join(["word " * 100] * 10)
    result = chunk(big)
    assert len(result) > 1


def test_parse_strips_nav():
    html = "<html><body><nav>skip</nav><p>keep</p></body></html>"
    result = parse(html)
    assert "keep" in result
    assert "skip" not in result
```

- [ ] **Step 4: Run all tests**

```bash
cd scraper
uv run pytest tests/ -v
```
Expected: All 13 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/server.py scraper/tests/test_namespaces.py
git commit -m "feat(scraper): add helper utilities"
```

---

### Task 4: index_page

**Files:**
- Modify: `scraper/server.py`
- Create: `scraper/tests/test_indexing.py`

- [ ] **Step 1: Write failing tests in `scraper/tests/test_indexing.py`**

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import server

SIMPLE_HTML = """
<html><body>
<h1>Hello</h1>
<p>This is some documentation content that should be indexed.</p>
</body></html>
"""

OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "summary": "List items",
                "tags": ["items"],
                "parameters": [],
            }
        }
    },
}


def make_html_response(body: str) -> MagicMock:
    resp = MagicMock()
    resp.text = body
    resp.headers = {"content-type": "text/html"}
    resp.json.side_effect = Exception("not json")
    return resp


def make_json_response(body: dict) -> MagicMock:
    resp = MagicMock()
    resp.text = json.dumps(body)
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = body
    return resp


@pytest.fixture
def ns():
    server._create_namespace(server._chroma_client, "test-ns")
    server._use_namespace(server._chroma_client, "test-ns")
    return server._current_collection


async def test_index_page_html(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        result = await server._index_page(ns, url)
    assert "Indexed" in result
    assert url in result
    assert ns.count() > 0


async def test_index_page_openapi(ns):
    url = "http://example.com/openapi.json"
    with patch("server._fetch", new=AsyncMock(return_value=make_json_response(OPENAPI_SPEC))):
        result = await server._index_page(ns, url)
    assert "operations" in result
    assert ns.count() > 0


async def test_index_page_no_namespace():
    result = await server._index_page_tool("http://example.com/docs")
    assert "No namespace selected" in result


async def test_index_page_fetch_failure(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=None)):
        result = await server._index_page(ns, url)
    assert "Failed" in result
```

- [ ] **Step 2: Run to verify failure**

```bash
cd scraper
uv run pytest tests/test_indexing.py -v
```
Expected: `AttributeError: module 'server' has no attribute '_index_page'`

- [ ] **Step 3: Add `_index_page` and `index_page` to `scraper/server.py`**

```python
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


async def _index_page_tool(url: str) -> str:
    if _current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    return await _index_page(_current_collection, url)


@mcp.tool()
async def index_page(url: str) -> str:
    """Fetch a documentation page and add it to the current namespace index."""
    return await _index_page_tool(url)
```

- [ ] **Step 4: Run tests**

```bash
cd scraper
uv run pytest tests/test_indexing.py -v
```
Expected: All 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/server.py scraper/tests/test_indexing.py
git commit -m "feat(scraper): add index_page tool"
```

---

### Task 5: index_tree

**Files:**
- Modify: `scraper/server.py`
- Modify: `scraper/tests/test_indexing.py`

- [ ] **Step 1: Add failing tests to `scraper/tests/test_indexing.py`**

```python
async def test_index_tree_single_page(ns):
    url = "http://example.com/"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        result = await server._index_tree(ns, url)
    assert "Indexed 1" in result


async def test_index_tree_skips_already_indexed(ns):
    url = "http://example.com/"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await server._index_tree(ns, url)
        result = await server._index_tree(ns, url)
    assert "skipped" in result


async def test_index_tree_no_namespace():
    result = await server._index_tree_tool("http://example.com/")
    assert "No namespace selected" in result
```

- [ ] **Step 2: Run to verify failure**

```bash
cd scraper
uv run pytest tests/test_indexing.py::test_index_tree_single_page -v
```
Expected: `AttributeError: module 'server' has no attribute '_index_tree'`

- [ ] **Step 3: Add `_index_tree` and `index_tree` to `scraper/server.py`**

```python
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


async def _index_tree_tool(url: str, max_depth: int = 2, force: bool = False, log=None) -> str:
    if _current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    return await _index_tree(_current_collection, url, max_depth, force, log)


@mcp.tool()
async def index_tree(url: str, ctx: Context, max_depth: int = 2, force: bool = False) -> str:
    """Fetch a documentation site and recursively index all pages on the same domain."""
    return await _index_tree_tool(url, max_depth, force, ctx.info)
```

- [ ] **Step 4: Run all tests**

```bash
cd scraper
uv run pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/server.py scraper/tests/test_indexing.py
git commit -m "feat(scraper): add index_tree tool"
```

---

### Task 6: discover_links

**Files:**
- Modify: `scraper/server.py`
- Modify: `scraper/tests/test_indexing.py`

- [ ] **Step 1: Add failing test to `scraper/tests/test_indexing.py`**

```python
LINKED_HTML = """
<html><body>
<a href="/page-a">Page A</a>
<a href="/page-b">Page B</a>
<a href="http://other.com/external">External</a>
</body></html>
"""


async def test_discover_links_same_domain_only():
    url = "http://example.com/"
    leaf = make_html_response("<html><body>leaf</body></html>")

    async def mock_fetch(u):
        if u == url:
            return make_html_response(LINKED_HTML)
        return leaf

    with patch("server._fetch", new=AsyncMock(side_effect=mock_fetch)):
        result = await server._discover_links(url, max_depth=1)

    assert url in result
    assert "http://example.com/page-a" in result
    assert "http://example.com/page-b" in result
    assert "http://other.com/external" not in result
```

- [ ] **Step 2: Run to verify failure**

```bash
cd scraper
uv run pytest tests/test_indexing.py::test_discover_links_same_domain_only -v
```
Expected: `AttributeError: module 'server' has no attribute '_discover_links'`

- [ ] **Step 3: Add `_discover_links` and `discover_links` to `scraper/server.py`**

```python
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


@mcp.tool()
async def discover_links(url: str, max_depth: int = 2) -> list[str]:
    """Discover all pages reachable from a URL within max_depth hops on the same domain."""
    return await _discover_links(url, max_depth)
```

- [ ] **Step 4: Run all tests**

```bash
cd scraper
uv run pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/server.py scraper/tests/test_indexing.py
git commit -m "feat(scraper): add discover_links tool"
```

---

### Task 7: list_indexed_pages, clear_index, search_docs

**Files:**
- Modify: `scraper/server.py`
- Create: `scraper/tests/test_search.py`

- [ ] **Step 1: Write failing tests in `scraper/tests/test_search.py`**

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import server

SIMPLE_HTML = """
<html><body>
<h1>Authentication Guide</h1>
<p>Use bearer tokens to authenticate API calls. Include the token in the Authorization header.</p>
</body></html>
"""


@pytest.fixture
def ns():
    server._create_namespace(server._chroma_client, "test-ns")
    server._use_namespace(server._chroma_client, "test-ns")
    return server._current_collection


def make_html_response(body: str) -> MagicMock:
    resp = MagicMock()
    resp.text = body
    resp.headers = {"content-type": "text/html"}
    resp.json.side_effect = Exception("not json")
    return resp


def test_list_indexed_pages_empty(ns):
    result = server._list_indexed_pages(ns)
    assert result == []


async def test_list_indexed_pages(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await server._index_page(ns, url)
    result = server._list_indexed_pages(ns)
    assert len(result) == 1
    assert result[0]["url"] == url
    assert result[0]["chunks"] > 0


async def test_clear_index(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await server._index_page(ns, url)
    assert ns.count() > 0
    result = server._clear_index(ns)
    assert "Deleted" in result
    assert ns.count() == 0


def test_clear_index_empty(ns):
    result = server._clear_index(ns)
    assert "already empty" in result.lower()


def test_search_docs_no_namespace():
    result = server._search_docs_tool("auth tokens")
    assert "No namespace selected" in result[0]["error"]


async def test_search_docs_returns_results(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await server._index_page(ns, url)
    results = server._search_docs(ns, "authentication bearer token")
    assert len(results) > 0
    assert "source_url" in results[0]
    assert "text" in results[0]
    assert "relevance_score" in results[0]
```

- [ ] **Step 2: Run to verify failure**

```bash
cd scraper
uv run pytest tests/test_search.py -v
```
Expected: `AttributeError: module 'server' has no attribute '_list_indexed_pages'`

- [ ] **Step 3: Add impl functions and MCP tools to `scraper/server.py`**

```python
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


def _search_docs(collection: chromadb.Collection, query: str, n_results: int = 5) -> list[dict]:
    results = collection.query(query_texts=[query], n_results=min(n_results, collection.count()))
    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "text": doc,
            "source_url": meta.get("source_url", "unknown"),
            "relevance_score": round(1 - dist, 3),
        })
    return output


def _search_docs_tool(query: str, n_results: int = 5) -> list[dict]:
    if _current_collection is None:
        return [{"error": "No namespace selected. Call use_namespace(name) first."}]
    if _current_collection.count() == 0:
        return [{"error": "Namespace is empty. Call index_page(url) first."}]
    return _search_docs(_current_collection, query, n_results)


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
def search_docs(query: str, n_results: int = 5) -> list[dict]:
    """Search the active namespace. Returns relevant chunks with source URLs."""
    return _search_docs_tool(query, n_results)
```

- [ ] **Step 4: Run full test suite**

```bash
cd scraper
uv run pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 5: Final smoke test — verify server starts**

```bash
cd scraper
uv run python server.py --help 2>&1 || uv run python -c "import server; print('server imports OK')"
```
Expected: No import errors.

- [ ] **Step 6: Commit**

```bash
git add scraper/server.py scraper/tests/test_search.py
git commit -m "feat(scraper): add list_indexed_pages, clear_index, search_docs tools"
```
