# REST Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a FastAPI HTTP layer to `scraper-mcp` that exposes every MCP tool as a REST endpoint so a frontend UI can interact with the scraper without going through the MCP protocol.

**Architecture:** `router.py` holds the FastAPI app, CORS middleware, Pydantic request models, and all route handlers. Handlers delegate directly to the existing private functions in `server.py`, sharing the same in-process globals (`_chroma_client`, `_current_collection`). `main()` in `server.py` is updated to run MCP (stdio) and uvicorn concurrently via `asyncio.gather`.

**Tech Stack:** FastAPI ≥ 0.115, uvicorn ≥ 0.34, httpx (already a dep, used in tests via `ASGITransport`), pytest-asyncio (already a dev-dep).

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `router.py` | FastAPI app, CORS, Pydantic models, all route handlers |
| Create | `tests/test_router.py` | Integration tests for all REST endpoints |
| Modify | `pyproject.toml` | Add fastapi and uvicorn dependencies |
| Modify | `server.py` | Update `main()` only — add async dual-server launch |

---

## Task 1: Add FastAPI and uvicorn dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dependencies to pyproject.toml**

In `pyproject.toml`, add two lines inside the `dependencies` list:

```toml
[project]
name = "scraper-mcp"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "beautifulsoup4>=4.14.3",
    "chromadb>=1.5.9",
    "fastapi>=0.115",
    "httpx>=0.28.1",
    "lxml>=6.1.1",
    "markdownify>=1.2.2",
    "mcp[cli]>=1.27.1",
    "tiktoken>=0.13.0",
    "uvicorn>=0.34",
]
```

- [ ] **Step 2: Install dependencies**

```bash
uv sync
```

Expected: resolves and installs fastapi and uvicorn without errors.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add fastapi and uvicorn dependencies"
```

---

## Task 2: Create router.py with namespace endpoints

**Files:**
- Create: `router.py`
- Create: `tests/test_router.py`

- [ ] **Step 1: Write failing tests for namespace endpoints**

Create `tests/test_router.py`:

```python
import httpx
import pytest
import server
from router import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_create_namespace(client):
    response = await client.post("/namespaces", json={"name": "my-ns"})
    assert response.status_code == 200
    assert "my-ns" in response.json()


async def test_create_namespace_invalid_name(client):
    response = await client.post("/namespaces", json={"name": "x"})
    assert response.status_code == 400


async def test_list_namespaces_empty(client):
    response = await client.get("/namespaces")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_namespaces_after_create(client):
    await client.post("/namespaces", json={"name": "ns-a"})
    await client.post("/namespaces", json={"name": "ns-b"})
    response = await client.get("/namespaces")
    assert "ns-a" in response.json()
    assert "ns-b" in response.json()


async def test_delete_namespace(client):
    await client.post("/namespaces", json={"name": "to-delete"})
    response = await client.delete("/namespaces/to-delete")
    assert response.status_code == 200
    assert "deleted" in response.json().lower()


async def test_delete_namespace_not_found(client):
    response = await client.delete("/namespaces/ghost")
    assert response.status_code == 400


async def test_use_namespace(client):
    await client.post("/namespaces", json={"name": "switch-to"})
    # create a second namespace so current_namespace changes
    await client.post("/namespaces", json={"name": "other"})
    response = await client.post("/namespaces/switch-to/use")
    assert response.status_code == 200
    assert "switch-to" in response.json()


async def test_use_namespace_not_found(client):
    response = await client.post("/namespaces/ghost/use")
    assert response.status_code == 400


async def test_current_namespace_none(client):
    response = await client.get("/namespaces/current")
    assert response.status_code == 200
    assert "No namespace" in response.json()


async def test_current_namespace_set(client):
    await client.post("/namespaces", json={"name": "active"})
    response = await client.get("/namespaces/current")
    assert response.status_code == 200
    assert response.json() == "active"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_router.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'router'`

- [ ] **Step 3: Create router.py with namespace endpoints**

Create `router.py`:

```python
import os

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import server

app = FastAPI(title="Scraper MCP REST API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_ERROR_MARKERS = (
    "Invalid name",
    "does not exist",
    "No namespace",
    "Failed to",
    "No content extracted",
)


def _raise_if_error(result: str) -> None:
    if any(marker in result for marker in _ERROR_MARKERS):
        raise HTTPException(status_code=400, detail=result)


class NamespaceBody(BaseModel):
    name: str


@app.post("/namespaces")
def create_namespace_route(body: NamespaceBody) -> str:
    result = server._create_namespace(server._chroma_client, body.name)
    _raise_if_error(result)
    return result


@app.get("/namespaces")
def list_namespaces_route() -> list[str]:
    return server._list_namespaces(server._chroma_client)


@app.delete("/namespaces/{name}")
def delete_namespace_route(name: str) -> str:
    result = server._delete_namespace(server._chroma_client, name)
    _raise_if_error(result)
    return result


@app.post("/namespaces/{name}/use")
def use_namespace_route(name: str) -> str:
    result = server._use_namespace(server._chroma_client, name)
    _raise_if_error(result)
    return result


@app.get("/namespaces/current")
def current_namespace_route() -> str:
    return server._current_namespace()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_router.py -v 2>&1 | head -40
```

Expected: all 10 namespace tests PASS.

- [ ] **Step 5: Commit**

```bash
git add router.py tests/test_router.py
git commit -m "feat: add REST router with namespace endpoints"
```

---

## Task 3: Add indexing endpoints

**Files:**
- Modify: `tests/test_router.py` — append indexing tests
- Modify: `router.py` — append indexing routes

- [ ] **Step 1: Write failing tests for indexing endpoints**

Append to `tests/test_router.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch


def _html_response(body: str) -> MagicMock:
    resp = MagicMock()
    resp.text = body
    resp.headers = {"content-type": "text/html"}
    resp.json.side_effect = Exception("not json")
    return resp


SIMPLE_HTML = "<html><body><h1>Hello</h1><p>Some documentation content here.</p></body></html>"


@pytest.fixture
async def ns_client(client):
    await client.post("/namespaces", json={"name": "test-ns"})
    return client


async def test_index_page_no_namespace(client):
    response = await client.post("/index/page", json={"url": "http://example.com"})
    assert response.status_code == 400


async def test_index_page_success(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        response = await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    assert response.status_code == 200
    assert "Indexed" in response.json()


async def test_index_page_fetch_failure(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=None)):
        response = await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    assert response.status_code == 400


async def test_index_tree_no_namespace(client):
    response = await client.post("/index/tree", json={"url": "http://example.com"})
    assert response.status_code == 400


async def test_index_tree_success(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        response = await ns_client.post("/index/tree", json={"url": "http://example.com"})
    assert response.status_code == 200
    assert "Indexed" in response.json()


async def test_list_indexed_pages_empty(ns_client):
    response = await ns_client.get("/index/pages")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_indexed_pages_after_indexing(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    response = await ns_client.get("/index/pages")
    assert response.status_code == 200
    assert any(p["url"] == "http://example.com/docs" for p in response.json())


async def test_clear_index_no_namespace(client):
    response = await client.delete("/index")
    assert response.status_code == 400


async def test_clear_index_success(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    response = await ns_client.delete("/index")
    assert response.status_code == 200
    assert "Deleted" in response.json()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_router.py -k "index" -v 2>&1 | head -30
```

Expected: FAIL with `404 Not Found` for the indexing routes.

- [ ] **Step 3: Add indexing routes to router.py**

Append to `router.py` (before the end of the file):

```python
class IndexPageBody(BaseModel):
    url: str


class IndexTreeBody(BaseModel):
    url: str
    max_depth: int = 2
    force: bool = False


@app.post("/index/page")
async def index_page_route(body: IndexPageBody) -> str:
    result = await server._index_page_tool(body.url)
    _raise_if_error(result)
    return result


@app.post("/index/tree")
async def index_tree_route(body: IndexTreeBody) -> str:
    result = await server._index_tree_tool(body.url, body.max_depth, body.force)
    _raise_if_error(result)
    return result


@app.get("/index/pages")
def list_indexed_pages_route() -> list[dict]:
    if server._current_collection is None:
        return []
    return server._list_indexed_pages(server._current_collection)


@app.delete("/index")
def clear_index_route() -> str:
    if server._current_collection is None:
        raise HTTPException(status_code=400, detail="No namespace selected. Call use_namespace first.")
    return server._clear_index(server._current_collection)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_router.py -v 2>&1 | tail -30
```

Expected: all tests PASS (namespace + indexing).

- [ ] **Step 5: Commit**

```bash
git add router.py tests/test_router.py
git commit -m "feat: add indexing REST endpoints"
```

---

## Task 4: Add search and discover endpoints

**Files:**
- Modify: `tests/test_router.py` — append search and discover tests
- Modify: `router.py` — append search and discover routes

- [ ] **Step 1: Write failing tests**

Append to `tests/test_router.py`:

```python
async def test_search_no_namespace(client):
    response = await client.get("/search", params={"query": "hello"})
    assert response.status_code == 400


async def test_search_success(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    response = await ns_client.get("/search", params={"query": "documentation", "n_results": 3})
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert "references" in body
    assert isinstance(body["results"], list)
    assert isinstance(body["references"], list)


async def test_discover_links(client):
    linked_html = (
        '<html><body>'
        '<a href="/page-a">A</a>'
        '<a href="http://other.com/ext">Ext</a>'
        '</body></html>'
    )
    leaf = _html_response("<html><body>leaf</body></html>")

    async def mock_fetch(url):
        if url == "http://example.com/":
            return _html_response(linked_html)
        return leaf

    with patch("server._fetch", new=AsyncMock(side_effect=mock_fetch)):
        response = await client.get("/links", params={"url": "http://example.com/", "max_depth": 1})

    assert response.status_code == 200
    links = response.json()
    assert "http://example.com/" in links
    assert "http://example.com/page-a" in links
    assert "http://other.com/ext" not in links
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_router.py -k "search or discover" -v 2>&1 | head -20
```

Expected: FAIL with `404 Not Found`.

- [ ] **Step 3: Add search and discover routes to router.py**

Append to `router.py`:

```python
@app.get("/search")
def search_route(query: str, n_results: int = 5) -> dict:
    result = server._search_docs_tool(query, n_results)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/links")
async def discover_links_route(url: str, max_depth: int = 2) -> list[str]:
    return await server._discover_links(url, max_depth)
```

- [ ] **Step 4: Run all tests to verify everything passes**

```bash
uv run pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests PASS, including pre-existing `test_indexing.py`, `test_namespaces.py`, `test_search.py`.

- [ ] **Step 5: Commit**

```bash
git add router.py tests/test_router.py
git commit -m "feat: add search and discover REST endpoints"
```

---

## Task 5: Update main() to run both servers

**Files:**
- Modify: `server.py` — `main()` function only

- [ ] **Step 1: Update main() in server.py**

Replace the existing `main()` and `if __name__ == "__main__":` block at the bottom of `server.py`:

```python
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
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
uv run pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests PASS. The updated `main()` is not called during tests.

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "feat: launch HTTP and MCP servers concurrently in main()"
```

---

## Done

All 11 MCP tools now have corresponding REST endpoints:

| Endpoint | Tool |
|----------|------|
| `POST /namespaces` | `create_namespace` |
| `GET /namespaces` | `list_namespaces` |
| `DELETE /namespaces/{name}` | `delete_namespace` |
| `POST /namespaces/{name}/use` | `use_namespace` |
| `GET /namespaces/current` | `current_namespace` |
| `POST /index/page` | `index_page` |
| `POST /index/tree` | `index_tree` |
| `GET /index/pages` | `list_indexed_pages` |
| `DELETE /index` | `clear_index` |
| `GET /search` | `search_docs` |
| `GET /links` | `discover_links` |

Auto-generated OpenAPI docs are available at `http://localhost:8000/docs` when the server is running.
