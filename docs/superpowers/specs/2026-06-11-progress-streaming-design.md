# Progress Streaming Design

**Date:** 2026-06-11
**Feature:** Live progress display in UI during `index-tree` and `discover-links` operations

## Problem

`index-tree` and `discover-links` are long-running HTTP operations. The UI currently shows a spinner but gives no feedback on what is happening. Users have no visibility into how many pages have been processed or which URLs are being crawled.

## Decisions

- **Progress style:** Live URL feed — scrolling list of URLs as they are processed, most recent at bottom.
- **After index-tree completes:** Summary line + full scrollable URL log. Failed URLs highlighted red.
- **After discover-links completes:** URL list stays as the final result (no extra summary needed; count shown in header).
- **Streaming mechanism:** Server-Sent Events (SSE) via two new GET endpoints.

## Architecture

Two new SSE endpoints, parallel to existing blocking endpoints (which stay unchanged for MCP/CLI callers):

```
GET /index/tree/stream?url=...&max_depth=2&force=false  →  text/event-stream
GET /links/stream?url=...&max_depth=2                    →  text/event-stream
```

SSE event format:

```json
{"type": "progress", "message": "[indexed] https://docs.example.com/api"}
{"type": "progress", "message": "[skipped] https://docs.example.com/intro"}
{"type": "progress", "message": "[failed] https://docs.example.com/broken"}
{"type": "done", "summary": "Indexed 17 pages (3 skipped, 1 failed) starting from …"}
```

For `discover-links`, progress events carry `{"type": "progress", "message": "https://…"}` and the final event is `{"type": "done", "count": 17}`.

An `asyncio.Queue` bridges the `log` callback inside `_index_tree` / `_discover_links` to the SSE generator. The generator drains the queue with a 0.1s timeout and emits keepalive comments between events.

## Backend Changes

### `server.py`

**`_index_tree`** — add two log calls alongside the existing skipped one:

```python
# after successful index:
if ok:
    indexed += 1
    if log:
        await log(f"[indexed] {current_url}")

# after fetch failure:
if response is None:
    failed += 1
    if log:
        await log(f"[failed] {current_url}")
    continue

# after index exception:
except Exception:
    failed += 1
    if log:
        await log(f"[failed] {current_url}")
    continue
```

**`_discover_links`** — add `log=None` parameter, call `await log(current_url)` for each URL appended to `found`. Existing REST caller at `/links` passes no log (behaviour unchanged).

### `router.py`

Two new endpoints using `StreamingResponse(media_type="text/event-stream")`:

**`GET /index/tree/stream`**

```python
@app.get("/index/tree/stream")
async def index_tree_stream_route(url: str, max_depth: int = 2, force: bool = False):
    if server._current_collection is None:
        raise HTTPException(400, "No namespace selected")
    queue = asyncio.Queue()
    async def log(msg): await queue.put(msg)
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
        summary = await task
        yield f"data: {json.dumps({'type': 'done', 'summary': summary})}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

**`GET /links/stream`** — same pattern, calls `server._discover_links(url, max_depth, log)`, final event is `{"type": "done", "count": len(found)}`.

## Frontend Changes

### `api.js`

Two new streaming functions. The existing `indexTree` and `discoverLinks` functions stay (used by tests and any non-UI callers).

```js
export function indexTreeStream(url, maxDepth, force, onEvent) {
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

export function discoverLinksStream(url, maxDepth, onEvent) {
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

### `App.jsx`

For `index-tree` and `discover-links`, the history entry is pushed immediately with `urls: [], status: 'pending'`. Each `progress` event appends to `entry.urls` via `setHistory` map. On `done`, sets `result` and `status: 'done'`.

`index-page` and `search` are unchanged (no streaming needed).

### `HistoryEntry.jsx`

New rendering branch for `index-tree` and `discover-links` when `entry.status === 'pending'`:

- Show a scrollable URL list (max height ~160px, overflow-y auto), auto-scrolling to bottom as URLs arrive.
- Current URL prefixed with `→`, completed with `✓` / `⚠` for failed.

When `status === 'done'` for `index-tree`:

- Summary line at top.
- Full scrollable URL log below (max height, overflow-y scroll). Lines containing `[failed]` rendered in red (`text-red-400`).

When `status === 'done'` for `discover-links`:

- `App.jsx` sets `entry.result = [...entry.urls]` on the done event. `HistoryEntry` renders via the existing `LinkListBody` (expects array). Count in header derives from `result.length` as today.

## Error Handling

- If `EventSource` fires `onerror`, the promise rejects and `App.jsx` sets `entry.error` as today.
- If the stream is mid-flight and the user navigates away, the browser closes the `EventSource` automatically; FastAPI's `generate()` will exit on the next yield when the client disconnects.
- The existing `/index/tree` POST and `/links` GET remain unchanged — no regression for MCP callers.

## Testing

- `server.py` changes (new log calls) are covered by existing `test_indexing.py` if the log callback is passed. Add a test that passes a log collector and asserts it receives `[indexed]`/`[failed]` messages.
- `router.py` SSE endpoints: add tests using `httpx`'s async client with streaming, asserting event sequence and final `done` event.
- Frontend: update `App.test.jsx` to mock `indexTreeStream` / `discoverLinksStream`. Update `HistoryEntry.test.jsx` for the new pending/done rendering paths.
