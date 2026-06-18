# Swagger UI Wrapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render OpenAPI/Swagger specs in Swagger UI instead of raw JSON/YAML, for both uploaded documents and indexed external URLs.

**Architecture:** Three new backend routes (`/swagger-ui`, `/proxy/spec`) serve a CDN-loaded Swagger UI page. The `is_openapi` flag is stored in ChromaDB metadata at index time and propagated to the frontend via `_list_indexed_pages`. The frontend routes `.json`/`.yaml`/`.yml` documents and `is_openapi` pages through the wrapper instead of linking directly to raw content.

**Tech Stack:** Python/FastAPI (backend), React/JSX + Tailwind (frontend), Swagger UI CDN (unpkg.com), httpx (proxy fetch), pytest + httpx.AsyncClient (backend tests), Vitest + React Testing Library (frontend tests).

## Global Constraints

- Zero new npm packages — Swagger UI loaded from CDN only
- Zero new Python packages — httpx already present
- All existing tests must continue to pass
- Backend tests use `chromadb.EphemeralClient()` (via conftest `reset_state` fixture — autouse)
- Frontend tests mock `api.js` at module level; `getDocumentUrl` is already imported in `DocumentsList`

---

### Task 1: Add `is_openapi` flag to ChromaDB metadata

**Files:**
- Modify: `server.py:686` (`_openapi_documents` — metadatas append)
- Modify: `server.py:289-297` (`_list_indexed_pages`)
- Modify: `tests/test_indexing.py` (add one test)
- Modify: `tests/test_documents.py` (add one test)

**Interfaces:**
- Produces: `_list_indexed_pages` returns `list[dict]` where each dict now has `{"url": str, "chunks": int, "is_openapi": bool}`
- Produces: ChromaDB metadata for OpenAPI entries includes `"is_openapi": True`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_indexing.py`:

```python
async def test_list_indexed_pages_flags_openapi(ns):
    url = "http://example.com/openapi.json"
    with patch("server._fetch", new=AsyncMock(return_value=make_json_response(OPENAPI_SPEC))):
        await server._index_page(ns, url)
    pages = server._list_indexed_pages(ns)
    assert len(pages) == 1
    assert pages[0]["url"] == url
    assert pages[0]["is_openapi"] is True


async def test_list_indexed_pages_html_not_openapi(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await server._index_page(ns, url)
    pages = server._list_indexed_pages(ns)
    assert len(pages) == 1
    assert pages[0]["is_openapi"] is False
```

Add to `tests/test_documents.py`:

```python
def test_index_file_openapi_json_sets_is_openapi_flag(ns, tmp_uploads):
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test API"},
        "paths": {"/items": {"get": {"operationId": "listItems", "summary": "List"}}},
    }
    path = _write(tmp_uploads, "api.json", json.dumps(spec))
    server._index_file(ns, "test-ns", path)
    metas = ns.get(where={"source_url": "file://test-ns/api.json"})["metadatas"]
    assert all(m.get("is_openapi") is True for m in metas)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_indexing.py::test_list_indexed_pages_flags_openapi tests/test_indexing.py::test_list_indexed_pages_html_not_openapi tests/test_documents.py::test_index_file_openapi_json_sets_is_openapi_flag -v
```

Expected: FAIL — `is_openapi` key missing from results / metadata.

- [ ] **Step 3: Add `is_openapi: True` to `_openapi_documents` metadata**

In `server.py`, find `_openapi_documents` (around line 686). Change:

```python
            metadatas.append({"source_url": url, "path": path, "method": method})
```

to:

```python
            metadatas.append({"source_url": url, "path": path, "method": method, "is_openapi": True})
```

- [ ] **Step 4: Update `_list_indexed_pages` to propagate the flag**

In `server.py`, replace `_list_indexed_pages` (lines 289-297):

```python
def _list_indexed_pages(collection: chromadb.Collection) -> list[dict]:
    if collection.count() == 0:
        return []
    metadatas = collection.get()["metadatas"]
    counts: dict[str, int] = {}
    openapi_urls: set[str] = set()
    for meta in metadatas:
        url = meta.get("source_url", "unknown")
        counts[url] = counts.get(url, 0) + 1
        if meta.get("is_openapi"):
            openapi_urls.add(url)
    return [
        {"url": url, "chunks": n, "is_openapi": url in openapi_urls}
        for url, n in sorted(counts.items())
    ]
```

- [ ] **Step 5: Run all three new tests to verify they pass**

```bash
uv run pytest tests/test_indexing.py::test_list_indexed_pages_flags_openapi tests/test_indexing.py::test_list_indexed_pages_html_not_openapi tests/test_documents.py::test_index_file_openapi_json_sets_is_openapi_flag -v
```

Expected: PASS all three.

- [ ] **Step 6: Run full test suite to verify no regressions**

```bash
uv run pytest
```

Expected: all existing tests pass.

- [ ] **Step 7: Commit**

```bash
git add server.py tests/test_indexing.py tests/test_documents.py
git commit -m "feat: add is_openapi flag to ChromaDB metadata and list_indexed_pages"
```

---

### Task 2: Add `/swagger-ui` and `/proxy/spec` routes

**Files:**
- Modify: `router.py` (add two routes, extend imports)
- Modify: `tests/test_router.py` (add four tests)

**Interfaces:**
- Consumes: `server._fetch(url)` — already exists, returns `httpx.Response | None`
- Produces: `GET /swagger-ui?url=<spec>` → 200 HTML; `GET /proxy/spec?url=<external>` → 200 JSON/YAML or 502

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_router.py`:

```python
async def test_swagger_ui_returns_html(client):
    response = await client.get("/swagger-ui", params={"url": "/documents/api.json"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "swagger-ui" in response.text.lower()
    assert "/documents/api.json" in response.text


async def test_swagger_ui_missing_url_param(client):
    response = await client.get("/swagger-ui")
    assert response.status_code == 422


async def test_proxy_spec_returns_content(client):
    mock_resp = MagicMock()
    mock_resp.content = b'{"openapi": "3.0.0"}'
    mock_resp.headers = {"content-type": "application/json"}
    with patch("server._fetch", new=AsyncMock(return_value=mock_resp)):
        response = await client.get("/proxy/spec", params={"url": "https://api.example.com/openapi.json"})
    assert response.status_code == 200
    assert response.content == b'{"openapi": "3.0.0"}'


async def test_proxy_spec_fetch_failure_returns_502(client):
    with patch("server._fetch", new=AsyncMock(return_value=None)):
        response = await client.get("/proxy/spec", params={"url": "https://api.example.com/openapi.json"})
    assert response.status_code == 502
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_router.py::test_swagger_ui_returns_html tests/test_router.py::test_swagger_ui_missing_url_param tests/test_router.py::test_proxy_spec_returns_content tests/test_router.py::test_proxy_spec_fetch_failure_returns_502 -v
```

Expected: FAIL — routes not found (404).

- [ ] **Step 3: Extend imports in `router.py`**

Change the existing import line:

```python
from fastapi.responses import FileResponse, StreamingResponse
```

to:

```python
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
```

- [ ] **Step 4: Add the two new routes to `router.py`**

Add before the `/search` route (after the `delete_document_route`):

```python
@app.get("/swagger-ui")
def swagger_ui_route(url: str):
    html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Swagger UI</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({{
      url: {json.dumps(url)},
      dom_id: '#swagger-ui',
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: 'StandaloneLayout'
    }})
  </script>
</body>
</html>"""
    return HTMLResponse(html)


@app.get("/proxy/spec")
async def proxy_spec_route(url: str):
    response = await server._fetch(url)
    if response is None:
        raise HTTPException(status_code=502, detail=f"Failed to fetch {url}")
    content_type = response.headers.get("content-type", "application/json")
    return Response(content=response.content, media_type=content_type)
```

- [ ] **Step 5: Run the four new tests**

```bash
uv run pytest tests/test_router.py::test_swagger_ui_returns_html tests/test_router.py::test_swagger_ui_missing_url_param tests/test_router.py::test_proxy_spec_returns_content tests/test_router.py::test_proxy_spec_fetch_failure_returns_502 -v
```

Expected: PASS all four.

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add router.py tests/test_router.py
git commit -m "feat: add /swagger-ui and /proxy/spec routes"
```

---

### Task 3: Route JSON/YAML documents through Swagger UI in `DocumentsList`

**Files:**
- Modify: `ui/src/components/DocumentsList.jsx`
- Modify: `ui/src/components/DocumentsList.test.jsx`

**Interfaces:**
- Consumes: `getDocumentUrl(name)` from `api.js` — used for non-swagger, non-browser files (download)
- Produces: `.json`/`.yaml`/`.yml` files link to `/swagger-ui?url=%2Fdocuments%2F<name>`

- [ ] **Step 1: Write the failing tests**

Add to `ui/src/components/DocumentsList.test.jsx` (inside the `describe` block):

```jsx
it('json file links to swagger-ui wrapper, opens in new tab', () => {
  const docs = [{ name: 'api.json', size: 512, content_type: 'application/json' }]
  render(<DocumentsList documents={docs} onUpload={vi.fn()} onDelete={vi.fn()} />)
  const link = screen.getByRole('link', { name: /api\.json/ })
  expect(link).toHaveAttribute('href', '/swagger-ui?url=%2Fdocuments%2Fapi.json')
  expect(link).toHaveAttribute('target', '_blank')
  expect(link).not.toHaveAttribute('download')
})

it('yaml file links to swagger-ui wrapper', () => {
  const docs = [{ name: 'spec.yaml', size: 256, content_type: 'application/yaml' }]
  render(<DocumentsList documents={docs} onUpload={vi.fn()} onDelete={vi.fn()} />)
  const link = screen.getByRole('link', { name: /spec\.yaml/ })
  expect(link).toHaveAttribute('href', '/swagger-ui?url=%2Fdocuments%2Fspec.yaml')
})

it('yml file links to swagger-ui wrapper', () => {
  const docs = [{ name: 'openapi.yml', size: 256, content_type: 'application/yaml' }]
  render(<DocumentsList documents={docs} onUpload={vi.fn()} onDelete={vi.fn()} />)
  const link = screen.getByRole('link', { name: /openapi\.yml/ })
  expect(link).toHaveAttribute('href', '/swagger-ui?url=%2Fdocuments%2Fopenapi.yml')
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ui && npx vitest run src/components/DocumentsList.test.jsx
```

Expected: FAIL — links point to raw document URL, not swagger-ui wrapper.

- [ ] **Step 3: Update `DocumentsList.jsx`**

Replace the two `const` declarations at the top of the file:

```jsx
const OPEN_IN_BROWSER = new Set(['.pdf', '.txt', '.md', '.json', '.yaml', '.yml'])
```

with:

```jsx
const SWAGGER_EXTS = new Set(['.json', '.yaml', '.yml'])
const OPEN_IN_BROWSER = new Set(['.pdf', '.txt', '.md'])
```

Replace the link-rendering block inside `documents.map(...)`. Find this section (around line 79):

```jsx
          const ext = getExt(doc.name)
          const url = getDocumentUrl(doc.name)
          const openInBrowser = OPEN_IN_BROWSER.has(ext)
          return (
            <div key={doc.name} className="flex items-center gap-1 group">
              {openInBrowser ? (
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  title={doc.name}
                  className="text-sky-400 text-[11px] no-underline truncate flex-1 hover:text-sky-300"
                >
                  {fileIcon(doc.name)} {doc.name}
                </a>
              ) : (
                <a
                  href={url}
                  download
                  title={doc.name}
                  className="text-sky-400 text-[11px] no-underline truncate flex-1 hover:text-sky-300"
                >
                  {fileIcon(doc.name)} {doc.name}
                </a>
              )}
```

Replace it with:

```jsx
          const ext = getExt(doc.name)
          const isSwagger = SWAGGER_EXTS.has(ext)
          const openInBrowser = OPEN_IN_BROWSER.has(ext)
          const href = isSwagger
            ? `/swagger-ui?url=${encodeURIComponent(`/documents/${doc.name}`)}`
            : getDocumentUrl(doc.name)
          return (
            <div key={doc.name} className="flex items-center gap-1 group">
              {isSwagger || openInBrowser ? (
                <a
                  href={href}
                  target="_blank"
                  rel="noreferrer"
                  title={doc.name}
                  className="text-sky-400 text-[11px] no-underline truncate flex-1 hover:text-sky-300"
                >
                  {fileIcon(doc.name)} {doc.name}
                </a>
              ) : (
                <a
                  href={href}
                  download
                  title={doc.name}
                  className="text-sky-400 text-[11px] no-underline truncate flex-1 hover:text-sky-300"
                >
                  {fileIcon(doc.name)} {doc.name}
                </a>
              )}
```

- [ ] **Step 4: Run the new tests**

```bash
cd ui && npx vitest run src/components/DocumentsList.test.jsx
```

Expected: all tests pass including the three new ones.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/DocumentsList.jsx ui/src/components/DocumentsList.test.jsx
git commit -m "feat: route json/yaml documents through swagger-ui wrapper"
```

---

### Task 4: Route OpenAPI pages through Swagger UI in `PagesList`

**Files:**
- Modify: `ui/src/components/PagesList.jsx`
- Modify: `ui/src/components/PagesList.test.jsx`

**Interfaces:**
- Consumes: `page.is_openapi: boolean` from the pages list (added by Task 1)
- Produces: pages with `is_openapi: true` link to `/swagger-ui?url=<encoded-proxy-url>` and show an `api` badge

- [ ] **Step 1: Write the failing tests**

Add to `ui/src/components/PagesList.test.jsx` (inside the `describe` block):

```jsx
it('openapi page links through swagger-ui proxy wrapper', async () => {
  const pages = [
    {
      url: 'https://api.example.com/openapi.json',
      chunks: 5,
      is_openapi: true,
    },
  ]
  render(<PagesList pages={pages} />)
  await userEvent.click(screen.getByText('api.example.com'))
  const link = screen.getByTitle('https://api.example.com/openapi.json')
  const expected = `/swagger-ui?url=${encodeURIComponent('/proxy/spec?url=' + encodeURIComponent('https://api.example.com/openapi.json'))}`
  expect(link).toHaveAttribute('href', expected)
  expect(link).toHaveAttribute('target', '_blank')
})

it('openapi page shows api badge', async () => {
  const pages = [
    {
      url: 'https://api.example.com/openapi.json',
      chunks: 5,
      is_openapi: true,
    },
  ]
  render(<PagesList pages={pages} />)
  await userEvent.click(screen.getByText('api.example.com'))
  expect(screen.getByText('api')).toBeInTheDocument()
})

it('non-openapi page links directly to its url', async () => {
  const pages = [{ url: 'https://docs.example.com/guide', chunks: 2, is_openapi: false }]
  render(<PagesList pages={pages} />)
  await userEvent.click(screen.getByText('docs.example.com'))
  const link = screen.getByTitle('https://docs.example.com/guide')
  expect(link).toHaveAttribute('href', 'https://docs.example.com/guide')
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ui && npx vitest run src/components/PagesList.test.jsx
```

Expected: FAIL — links still point directly to page URLs.

- [ ] **Step 3: Update `buildTree` to carry `is_openapi` through the tree**

In `PagesList.jsx`, find `buildTree` (lines 3-23). Change:

```js
      node.pages.push({ url: page.url, label })
```

to:

```js
      node.pages.push({ url: page.url, label, is_openapi: !!page.is_openapi })
```

- [ ] **Step 4: Update `TreeChildren` to render OpenAPI pages differently**

In `PagesList.jsx`, find the `TreeChildren` component (lines 41-61). Replace the `node.pages.map` block:

```jsx
      {node.pages.map((page) => (
        <a
          key={page.url}
          href={page.url}
          target="_blank"
          rel="noreferrer"
          title={page.url}
          className="text-sky-400 text-[11px] no-underline whitespace-nowrap block py-0.5 hover:text-sky-300"
        >
          {page.label}
        </a>
      ))}
```

with:

```jsx
      {node.pages.map((page) => {
        const href = page.is_openapi
          ? `/swagger-ui?url=${encodeURIComponent(`/proxy/spec?url=${encodeURIComponent(page.url)}`)}`
          : page.url
        return (
          <a
            key={page.url}
            href={href}
            target="_blank"
            rel="noreferrer"
            title={page.url}
            className="text-sky-400 text-[11px] no-underline whitespace-nowrap block py-0.5 hover:text-sky-300"
          >
            {page.label}
            {page.is_openapi && (
              <span className="ml-1 text-[9px] text-slate-500 uppercase tracking-wide">api</span>
            )}
          </a>
        )
      })}
```

- [ ] **Step 5: Run all PagesList tests**

```bash
cd ui && npx vitest run src/components/PagesList.test.jsx
```

Expected: all tests pass including the three new ones.

- [ ] **Step 6: Run full frontend test suite**

```bash
cd ui && npm test
```

Expected: all tests pass.

- [ ] **Step 7: Run full backend test suite**

```bash
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add ui/src/components/PagesList.jsx ui/src/components/PagesList.test.jsx
git commit -m "feat: route openapi pages through swagger-ui wrapper with api badge"
```
