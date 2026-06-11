# Progress Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream live URL progress to the UI during `index-tree` and `discover-links` operations via Server-Sent Events.

**Architecture:** Two new SSE GET endpoints (`/index/tree/stream`, `/links/stream`) stream progress events as pages are crawled. An `asyncio.Queue` bridges the internal `log` callback to the SSE generator. The frontend uses native `EventSource` to receive events and render a live URL feed; on completion, `index-tree` shows a summary + scrollable log, `discover-links` keeps the URL list as its result.

**Tech Stack:** Python asyncio + FastAPI StreamingResponse (backend), native EventSource API (frontend), React state updates via `setHistory` map, Vitest + pytest

---

## File Map

| File | Change |
|------|--------|
| `server.py` | Add `[indexed]`/`[failed]` log calls in `_index_tree`; add `log=None` param to `_discover_links` |
| `router.py` | Add `asyncio`, `json`, `StreamingResponse` imports; add two SSE endpoints |
| `tests/test_indexing.py` | Tests for new log calls |
| `tests/test_router.py` | Tests for SSE endpoints |
| `ui/src/api.js` | Add `indexTreeStream`, `discoverLinksStream` |
| `ui/src/api.test.js` | Tests for streaming functions using mocked `EventSource` |
| `ui/src/App.jsx` | Use streaming functions for index-tree/discover; push entry immediately with `urls`, `status` |
| `ui/src/App.test.jsx` | Mock streaming functions; add streaming result tests |
| `ui/src/components/HistoryEntry.jsx` | Handle `urls`/`status` fields; add `UrlFeed` and `IndexTreeBody` components |
| `ui/src/components/HistoryEntry.test.jsx` | Tests for pending live feed and done URL log states |

---

## Task 1: Add `[indexed]` and `[failed]` log calls to `_index_tree`

**Files:**
- Modify: `server.py` (around lines 214–231)
- Modify: `tests/test_indexing.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_indexing.py`:

```python
async def test_index_tree_log_indexed(ns):
    url = "http://example.com/"
    logged = []
    async def collect(msg): logged.append(msg)
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await server._index_tree(ns, url, log=collect)
    assert any("[indexed]" in m and url in m for m in logged)


async def test_index_tree_log_failed_fetch(ns):
    url = "http://example.com/"
    logged = []
    async def collect(msg): logged.append(msg)
    with patch("server._fetch", new=AsyncMock(return_value=None)):
        await server._index_tree(ns, url, log=collect)
    assert any("[failed]" in m and url in m for m in logged)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_indexing.py::test_index_tree_log_indexed tests/test_indexing.py::test_index_tree_log_failed_fetch -v
```

Expected: FAIL — no `[indexed]` or `[failed]` messages logged.

- [ ] **Step 3: Add log calls to `_index_tree` in `server.py`**

Find the `_index_tree` function (starting around line 189). Make these three additions:

After `if response is None:` / `failed += 1` / `continue` block — add log call before `continue`:
```python
        response = await _fetch(current_url)
        if response is None:
            failed += 1
            if log:
                await log(f"[failed] {current_url}")
            continue
```

After the `except Exception:` / `failed += 1` / `continue` block — add log call before `continue`:
```python
        except Exception:
            failed += 1
            if log:
                await log(f"[failed] {current_url}")
            continue
```

After `if ok:` / `indexed += 1` — add log call:
```python
        if ok:
            indexed += 1
            if log:
                await log(f"[indexed] {current_url}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_indexing.py -v
```

Expected: all pass including the two new tests.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_indexing.py
git commit -m "feat: add [indexed]/[failed] log calls to _index_tree"
```

---

## Task 2: Add `log` parameter to `_discover_links`

**Files:**
- Modify: `server.py` (lines 291–308)
- Modify: `tests/test_indexing.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_indexing.py`:

```python
async def test_discover_links_log_callback():
    url = "http://example.com/"
    logged = []
    async def collect(u): logged.append(u)
    leaf = make_html_response("<html><body>leaf</body></html>")
    with patch("server._fetch", new=AsyncMock(return_value=leaf)):
        result = await server._discover_links(url, max_depth=0, log=collect)
    assert url in logged
    assert url in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_indexing.py::test_discover_links_log_callback -v
```

Expected: FAIL — `_discover_links` doesn't accept `log` keyword argument.

- [ ] **Step 3: Update `_discover_links` in `server.py`**

Change the signature and add the log call. Find `_discover_links` (line 291):

```python
async def _discover_links(url: str, max_depth: int = 2, log=None) -> list[str]:
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(url, 0)])
    found: list[str] = []

    while queue:
        current_url, depth = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)
        found.append(current_url)
        if log:
            await log(current_url)

        if depth < max_depth:
            response = await _fetch(current_url)
            if response and "json" not in response.headers.get("content-type", ""):
                _enqueue_links(response.text, current_url, depth, visited, queue)

    return found
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_indexing.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_indexing.py
git commit -m "feat: add log callback to _discover_links"
```

---

## Task 3: Add SSE `/index/tree/stream` endpoint

**Files:**
- Modify: `router.py`
- Modify: `tests/test_router.py`

- [ ] **Step 1: Write the failing tests**

Add `import json` to the top of `tests/test_router.py` (alongside existing imports).

Add these tests:

```python
async def test_index_tree_stream_no_namespace(client):
    response = await client.get("/index/tree/stream", params={"url": "http://example.com"})
    assert response.status_code == 400


async def test_index_tree_stream_success(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        async with ns_client.stream(
            "GET", "/index/tree/stream", params={"url": "http://example.com/"}
        ) as resp:
            assert resp.status_code == 200
            events = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

    assert events[-1]["type"] == "done"
    assert "Indexed" in events[-1]["summary"]
    assert any(e["type"] == "progress" for e in events)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_router.py::test_index_tree_stream_no_namespace tests/test_router.py::test_index_tree_stream_success -v
```

Expected: FAIL — endpoint doesn't exist yet.

- [ ] **Step 3: Add imports and endpoint to `router.py`**

Add at the top of `router.py`, after `import logging`:

```python
import asyncio
import json
```

Add after the existing `from fastapi import FastAPI, HTTPException` line:

```python
from fastapi.responses import StreamingResponse
```

Add the new endpoint after the existing `index_tree_route` (after line ~105):

```python
@app.get("/index/tree/stream")
async def index_tree_stream_route(url: str, max_depth: int = 2, force: bool = False):
    if server._current_collection is None:
        raise HTTPException(status_code=400, detail="No namespace selected. Call use_namespace first.")
    queue: asyncio.Queue = asyncio.Queue()

    async def log(msg: str) -> None:
        await queue.put(msg)

    async def generate():
        task = asyncio.create_task(
            server._index_tree(server._current_collection, url, max_depth, force, log)
        )
        while not task.done():
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
        while not queue.empty():
            msg = queue.get_nowait()
            yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"
        summary = await task
        yield f"data: {json.dumps({'type': 'done', 'summary': summary})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_router.py -v
```

Expected: all pass including two new tests.

- [ ] **Step 5: Commit**

```bash
git add router.py tests/test_router.py
git commit -m "feat: add SSE /index/tree/stream endpoint"
```

---

## Task 4: Add SSE `/links/stream` endpoint

**Files:**
- Modify: `router.py`
- Modify: `tests/test_router.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_router.py`:

```python
async def test_discover_links_stream_success(client):
    linked_html = '<html><body><a href="/page-a">A</a></body></html>'

    async def mock_fetch(url):
        if url == "http://example.com/":
            return _html_response(linked_html)
        return _html_response("<html><body>leaf</body></html>")

    with patch("server._fetch", new=AsyncMock(side_effect=mock_fetch)):
        async with client.stream(
            "GET", "/links/stream", params={"url": "http://example.com/", "max_depth": 1}
        ) as resp:
            assert resp.status_code == 200
            events = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

    assert events[-1]["type"] == "done"
    assert any(e["type"] == "progress" and "example.com" in e["message"] for e in events)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_router.py::test_discover_links_stream_success -v
```

Expected: FAIL — endpoint doesn't exist.

- [ ] **Step 3: Add endpoint to `router.py`**

Add after the existing `discover_links_route` (after line ~132):

```python
@app.get("/links/stream")
async def discover_links_stream_route(url: str, max_depth: int = 2):
    queue: asyncio.Queue = asyncio.Queue()
    found: list[str] = []

    async def log(u: str) -> None:
        found.append(u)
        await queue.put(u)

    async def generate():
        task = asyncio.create_task(server._discover_links(url, max_depth, log))
        while not task.done():
            try:
                u = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield f"data: {json.dumps({'type': 'progress', 'message': u})}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
        while not queue.empty():
            u = queue.get_nowait()
            yield f"data: {json.dumps({'type': 'progress', 'message': u})}\n\n"
        await task
        yield f"data: {json.dumps({'type': 'done', 'count': len(found)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_router.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add router.py tests/test_router.py
git commit -m "feat: add SSE /links/stream endpoint"
```

---

## Task 5: Add streaming functions to `api.js`

**Files:**
- Modify: `ui/src/api.js`
- Modify: `ui/src/api.test.js`

- [ ] **Step 1: Write the failing tests**

Add to `ui/src/api.test.js`:

Add `indexTreeStream, discoverLinksStream` to the import at the top:
```js
import {
  listNamespaces, currentNamespace, createNamespace, useNamespace, deleteNamespace,
  listIndexedPages, indexPage, indexTree, searchDocs, discoverLinks,
  indexTreeStream, discoverLinksStream,
} from './api'
```

Add these test suites after the existing ones:

```js
describe('indexTreeStream', () => {
  let mockEs

  beforeEach(() => {
    mockEs = { onmessage: null, onerror: null, close: vi.fn() }
    vi.stubGlobal('EventSource', vi.fn(() => mockEs))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('opens EventSource at /index/tree/stream with params', () => {
    indexTreeStream('http://example.com/', 2, false, vi.fn())
    expect(EventSource).toHaveBeenCalledWith(
      '/index/tree/stream?url=http%3A%2F%2Fexample.com%2F&max_depth=2&force=false'
    )
  })

  it('calls onEvent for progress events and resolves with summary on done', async () => {
    const onEvent = vi.fn()
    const promise = indexTreeStream('http://example.com/', 2, false, onEvent)

    mockEs.onmessage({ data: JSON.stringify({ type: 'progress', message: '[indexed] http://example.com/' }) })
    mockEs.onmessage({ data: JSON.stringify({ type: 'done', summary: 'Indexed 1 page (0 skipped, 0 failed)' }) })

    const result = await promise
    expect(result).toBe('Indexed 1 page (0 skipped, 0 failed)')
    expect(onEvent).toHaveBeenCalledWith({ type: 'progress', message: '[indexed] http://example.com/' })
    expect(mockEs.close).toHaveBeenCalled()
  })

  it('rejects and closes on stream error', async () => {
    const promise = indexTreeStream('http://example.com/', 2, false, vi.fn())
    mockEs.onerror()
    await expect(promise).rejects.toThrow('Stream error')
    expect(mockEs.close).toHaveBeenCalled()
  })
})

describe('discoverLinksStream', () => {
  let mockEs

  beforeEach(() => {
    mockEs = { onmessage: null, onerror: null, close: vi.fn() }
    vi.stubGlobal('EventSource', vi.fn(() => mockEs))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('opens EventSource at /links/stream with params', () => {
    discoverLinksStream('http://example.com/', 2, vi.fn())
    expect(EventSource).toHaveBeenCalledWith(
      '/links/stream?url=http%3A%2F%2Fexample.com%2F&max_depth=2'
    )
  })

  it('calls onEvent for progress events and resolves on done', async () => {
    const onEvent = vi.fn()
    const promise = discoverLinksStream('http://example.com/', 2, onEvent)

    mockEs.onmessage({ data: JSON.stringify({ type: 'progress', message: 'http://example.com/' }) })
    mockEs.onmessage({ data: JSON.stringify({ type: 'done', count: 1 }) })

    await promise
    expect(onEvent).toHaveBeenCalledWith({ type: 'progress', message: 'http://example.com/' })
    expect(mockEs.close).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ui && npm test -- api.test.js
```

Expected: FAIL — `indexTreeStream` and `discoverLinksStream` not found.

- [ ] **Step 3: Add streaming functions to `api.js`**

Append to the end of `ui/src/api.js`:

```js
export function indexTreeStream(url, maxDepth = 2, force = false, onEvent) {
  const params = new URLSearchParams({ url, max_depth: maxDepth, force })
  const es = new EventSource(`/index/tree/stream?${params}`)
  return new Promise((resolve, reject) => {
    es.onmessage = e => {
      const ev = JSON.parse(e.data)
      onEvent(ev)
      if (ev.type === 'done') { es.close(); resolve(ev.summary) }
    }
    es.onerror = () => { es.close(); reject(new Error('Stream error')) }
  })
}

export function discoverLinksStream(url, maxDepth = 2, onEvent) {
  const params = new URLSearchParams({ url, max_depth: maxDepth })
  const es = new EventSource(`/links/stream?${params}`)
  return new Promise((resolve, reject) => {
    es.onmessage = e => {
      const ev = JSON.parse(e.data)
      onEvent(ev)
      if (ev.type === 'done') { es.close(); resolve() }
    }
    es.onerror = () => { es.close(); reject(new Error('Stream error')) }
  })
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ui && npm test -- api.test.js
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add ui/src/api.js ui/src/api.test.js
git commit -m "feat: add indexTreeStream and discoverLinksStream to api.js"
```

---

## Task 6: Update `App.jsx` to use streaming functions

**Files:**
- Modify: `ui/src/App.jsx`
- Modify: `ui/src/App.test.jsx`

- [ ] **Step 1: Write the failing tests**

In `ui/src/App.test.jsx`, add mock setup in `beforeEach` (alongside existing mocks):

```js
api.indexTreeStream.mockImplementation(async (_url, _depth, _force, onEvent) => {
    onEvent({ type: 'done', summary: 'Indexed tree.' })
    return 'Indexed tree.'
})
api.discoverLinksStream.mockImplementation(async (_url, _depth, onEvent) => {
    onEvent({ type: 'done' })
})
```

Add these tests inside the `describe('App', ...)` block:

```js
it('uses indexTreeStream for index-tree tool and shows result', async () => {
    api.indexTreeStream.mockImplementation(async (_url, _depth, _force, onEvent) => {
        onEvent({ type: 'progress', message: '[indexed] http://example.com/' })
        onEvent({ type: 'done', summary: 'Indexed 1 page (0 skipped, 0 failed)' })
        return 'Indexed 1 page (0 skipped, 0 failed)'
    })
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))
    await userEvent.click(screen.getByLabelText('Index Tree'))
    await userEvent.type(screen.getByPlaceholderText('https://docs.example.com/'), 'http://example.com/')
    await userEvent.click(screen.getByRole('button', { name: 'Index' }))
    await waitFor(() => expect(screen.getByText(/Indexed 1 page/)).toBeInTheDocument())
})

it('uses discoverLinksStream for discover tool and shows links', async () => {
    api.discoverLinksStream.mockImplementation(async (_url, _depth, onEvent) => {
        onEvent({ type: 'progress', message: 'http://example.com/' })
        onEvent({ type: 'done' })
    })
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))
    await userEvent.click(screen.getByLabelText('Discover Links'))
    await userEvent.type(screen.getByPlaceholderText('https://docs.example.com/'), 'http://example.com/')
    await userEvent.click(screen.getByRole('button', { name: 'Discover' }))
    await waitFor(() => expect(screen.getByText('http://example.com/')).toBeInTheDocument())
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ui && npm test -- App.test.jsx
```

Expected: new tests FAIL — `indexTreeStream` is not a function on the mock.

- [ ] **Step 3: Replace `handleSubmit` in `App.jsx`**

Replace the entire `handleSubmit` callback (lines 35–55) with:

```jsx
const handleSubmit = useCallback(async ({ value, depth }) => {
    setLoading(true)
    const entry = { id: Date.now(), tool, query: value, depth, result: null, error: null, urls: [], status: 'done' }

    if (tool === 'index-tree' || tool === 'discover') {
        entry.status = 'pending'
        setHistory(prev => [entry, ...prev])
        const collected = []
        const onEvent = (ev) => {
            if (ev.type === 'progress') {
                collected.push(ev.message)
                setHistory(prev => prev.map(e =>
                    e.id === entry.id ? { ...e, urls: [...collected] } : e
                ))
            }
        }
        try {
            if (tool === 'index-tree') {
                const summary = await api.indexTreeStream(value, depth, false, onEvent)
                setHistory(prev => prev.map(e =>
                    e.id === entry.id ? { ...e, result: summary, status: 'done' } : e
                ))
                refreshPages()
            } else {
                await api.discoverLinksStream(value, depth, onEvent)
                setHistory(prev => prev.map(e =>
                    e.id === entry.id ? { ...e, result: [...collected], status: 'done' } : e
                ))
            }
        } catch (err) {
            setHistory(prev => prev.map(e =>
                e.id === entry.id ? { ...e, error: err.message, status: 'done' } : e
            ))
        }
        setLoading(false)
        return
    }

    try {
        if (tool === 'search') {
            entry.result = await api.searchDocs(value)
        } else if (tool === 'index-page') {
            entry.result = await api.indexPage(value)
            refreshPages()
        }
    } catch (e) {
        entry.error = e.message
    }
    setHistory(prev => [entry, ...prev])
    setLoading(false)
}, [tool, refreshPages])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ui && npm test -- App.test.jsx
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add ui/src/App.jsx ui/src/App.test.jsx
git commit -m "feat: use streaming API for index-tree and discover in App.jsx"
```

---

## Task 7: Update `HistoryEntry.jsx` for live feed and URL log

**Files:**
- Modify: `ui/src/components/HistoryEntry.jsx`
- Modify: `ui/src/components/HistoryEntry.test.jsx`

- [ ] **Step 1: Write the failing tests**

Add to `ui/src/components/HistoryEntry.test.jsx`:

```jsx
const pendingTreeEntry = {
  id: 5,
  tool: 'index-tree',
  query: 'https://docs.example.com/',
  depth: 2,
  result: null,
  error: null,
  urls: ['[indexed] https://docs.example.com/', '[failed] https://docs.example.com/broken'],
  status: 'pending',
}

const doneTreeEntryWithLog = {
  id: 6,
  tool: 'index-tree',
  query: 'https://docs.example.com/',
  depth: 2,
  result: 'Indexed 1 page (0 skipped, 1 failed) starting from https://docs.example.com/',
  error: null,
  urls: ['[indexed] https://docs.example.com/', '[failed] https://docs.example.com/broken'],
  status: 'done',
}

describe('HistoryEntry — index-tree pending', () => {
  it('renders live URL feed with indexed and failed messages', () => {
    render(<HistoryEntry entry={pendingTreeEntry} faded={false} />)
    expect(screen.getByText('[indexed] https://docs.example.com/')).toBeInTheDocument()
    expect(screen.getByText('[failed] https://docs.example.com/broken')).toBeInTheDocument()
  })

  it('renders failed URL in red', () => {
    render(<HistoryEntry entry={pendingTreeEntry} faded={false} />)
    const el = screen.getByText('[failed] https://docs.example.com/broken')
    expect(el).toHaveClass('text-red-400')
  })

  it('shows ⋯ as summary while pending', () => {
    render(<HistoryEntry entry={pendingTreeEntry} faded={false} />)
    expect(screen.getByText('⋯')).toBeInTheDocument()
  })
})

describe('HistoryEntry — index-tree done with URL log', () => {
  it('renders summary and URL log', () => {
    render(<HistoryEntry entry={doneTreeEntryWithLog} faded={false} />)
    expect(screen.getByText(/Indexed 1 page/)).toBeInTheDocument()
    expect(screen.getByText('[indexed] https://docs.example.com/')).toBeInTheDocument()
  })

  it('renders failed URL in red in done log', () => {
    render(<HistoryEntry entry={doneTreeEntryWithLog} faded={false} />)
    const el = screen.getByText('[failed] https://docs.example.com/broken')
    expect(el).toHaveClass('text-red-400')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ui && npm test -- HistoryEntry.test.jsx
```

Expected: new tests FAIL — `HistoryEntry` doesn't handle `status` or `urls`.

- [ ] **Step 3: Rewrite `HistoryEntry.jsx`**

Replace the entire file content:

```jsx
import { useState, useRef, useEffect } from 'react'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const TOOL_CONFIG = {
  'search':     { icon: '🔍', label: 'Search',        color: 'text-indigo-400' },
  'index-page': { icon: '📄', label: 'Index Page',    color: 'text-emerald-400' },
  'index-tree': { icon: '🌲', label: 'Index Tree',    color: 'text-orange-400' },
  'discover':   { icon: '🔗', label: 'Discover Links', color: 'text-pink-400'   },
}

function SearchResult({ r }) {
  const [expanded, setExpanded] = useState(false)
  const long = r.text.length > 300
  return (
    <div className="border-l-2 border-blue-900 pl-2.5">
      <div
        className={`prose prose-invert prose-sm max-w-none mb-0.5 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0${expanded ? ' max-h-64 overflow-y-auto' : ''}`}
        dangerouslySetInnerHTML={{ __html: marked(long && !expanded ? r.text.slice(0, 300) + '…' : r.text) }}
      />
      {long && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-[10px] text-slate-500 hover:text-slate-300 mb-0.5"
        >
          {expanded ? 'show less' : 'show more'}
        </button>
      )}
      {r.source_url && (
        <a href={r.source_url} target="_blank" rel="noreferrer" className="text-[10px] text-sky-400 no-underline block">
          {r.source_url}
        </a>
      )}
    </div>
  )
}

function SearchBody({ result }) {
  return (
    <div className="flex flex-col gap-2">
      {result.results.map((r, i) => <SearchResult key={i} r={r} />)}
    </div>
  )
}

function LinkListBody({ links }) {
  return (
    <div className="flex flex-col gap-1">
      {links.map((url, i) => (
        <a key={i} href={url} target="_blank" rel="noreferrer" className="text-[11px] text-sky-400 no-underline">
          {url}
        </a>
      ))}
    </div>
  )
}

function UrlLog({ urls }) {
  const bottomRef = useRef(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [urls.length])
  return (
    <div className="max-h-40 overflow-y-auto flex flex-col gap-0.5">
      {urls.map((msg, i) => (
        <span key={i} className={`text-[11px] ${msg.includes('[failed]') ? 'text-red-400' : 'text-slate-500'}`}>
          {msg}
        </span>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

function IndexTreeBody({ result, urls }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-slate-400 leading-relaxed">{result}</p>
      {urls.length > 0 && (
        <div className="border-t border-slate-800 pt-2">
          <UrlLog urls={urls} />
        </div>
      )}
    </div>
  )
}

export default function HistoryEntry({ entry, faded = false }) {
  const { tool, query, depth, result, error, urls = [], status = 'done' } = entry
  const tc = TOOL_CONFIG[tool] ?? { icon: '?', label: tool, color: 'text-slate-400' }
  const [collapsed, setCollapsed] = useState(faded)
  const isPending = status === 'pending'

  const summary = error ? 'error'
    : isPending ? '⋯'
    : tool === 'search' ? `${result.results.length} results`
    : tool === 'discover' ? `${result.length} links`
    : '✓ done'

  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-lg overflow-hidden${faded ? ' opacity-45' : ''}`}>
      <div
        onClick={() => faded && setCollapsed(c => !c)}
        className={`flex items-center gap-2 px-3.5 py-2 border-b border-slate-800 bg-slate-950${faded ? ' cursor-pointer hover:bg-slate-900' : ''}`}
      >
        <span className="text-sm">{tc.icon}</span>
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${tc.color}`}>{tc.label}</span>
        <span className="flex-1 text-[11px] text-slate-400 truncate">
          {query}{depth != null ? ` · depth ${depth}` : ''}
        </span>
        <span className="text-[10px] text-slate-600 whitespace-nowrap">{summary}</span>
        {faded && <span className="text-[10px] text-slate-700">{collapsed ? '▸' : '▾'}</span>}
      </div>
      {!collapsed && (
        <div className="px-3.5 py-2.5 flex flex-col gap-2">
          {error && <p className="text-xs text-red-400">{error}</p>}
          {!error && tool === 'search' && <SearchBody result={result} />}
          {!error && tool === 'discover' && !isPending && <LinkListBody links={result} />}
          {!error && tool === 'index-tree' && !isPending && <IndexTreeBody result={result} urls={urls} />}
          {!error && tool === 'index-page' && (
            <p className="text-xs text-slate-400 leading-relaxed">{result}</p>
          )}
          {!error && isPending && <UrlLog urls={urls} />}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run all frontend tests to verify they pass**

```bash
cd ui && npm test
```

Expected: all pass, including existing tests (existing entries without `urls`/`status` use defaults).

- [ ] **Step 5: Run all backend tests**

```bash
uv run pytest
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/HistoryEntry.jsx ui/src/components/HistoryEntry.test.jsx
git commit -m "feat: add live URL feed and URL log to HistoryEntry"
```

---

## Final Verification

- [ ] **Build the UI and start the server**

```bash
cd ui && npm run build && cd .. && uv run python server.py
```

- [ ] **Open http://localhost:8000/ui and manually test:**
  - Select "Index Tree", enter a URL, submit — verify live URL feed appears while crawling, then transitions to summary + URL log
  - Select "Discover Links", enter a URL, submit — verify URLs stream in live, then stay as clickable links
  - Select "Index Page" and "Search" — verify no regression (still work as before)
