# REST Controller Design

**Date:** 2026-06-11
**Status:** Approved

## Goal

Add a FastAPI HTTP layer that mirrors every MCP tool as a REST endpoint, so a frontend UI can call the scraper's capabilities over HTTP without going through the MCP protocol.

## Architecture

Two files carry all the work:

- **`router.py`** — FastAPI app, all route handlers, Pydantic request models, CORS middleware. Handlers call the existing private functions in `server.py` directly; no business logic is duplicated.
- **`server.py`** — unchanged except `main()` is updated to run MCP (stdio) and uvicorn concurrently via `asyncio.gather`.

```
server.py    MCP tools + private functions + globals + main()
router.py    FastAPI app + route handlers (imports from server.py)
```

Both processes share the same `_chroma_client` and `_current_collection` globals because they run in the same Python process.

## Dependencies

Add to `pyproject.toml`:

```
fastapi>=0.115
uvicorn>=0.34
```

## Endpoints

| Method   | Path                      | MCP tool            |
|----------|---------------------------|---------------------|
| `POST`   | `/namespaces`             | `create_namespace`  |
| `GET`    | `/namespaces`             | `list_namespaces`   |
| `DELETE` | `/namespaces/{name}`      | `delete_namespace`  |
| `POST`   | `/namespaces/{name}/use`  | `use_namespace`     |
| `GET`    | `/namespaces/current`     | `current_namespace` |
| `POST`   | `/index/page`             | `index_page`        |
| `POST`   | `/index/tree`             | `index_tree`        |
| `GET`    | `/index/pages`            | `list_indexed_pages`|
| `DELETE` | `/index`                  | `clear_index`       |
| `GET`    | `/links`                  | `discover_links`    |
| `GET`    | `/search`                 | `search_docs`       |

## Request / Response

Request bodies are Pydantic models where input is required (e.g. `{"name": "my-ns"}` for namespace creation, `{"url": "https://..."}` for indexing). Query parameters are used for `GET` endpoints (e.g. `?query=foo&n_results=5` for search, `?url=...&max_depth=2` for discover/index-tree).

Responses are the raw return values of the private functions serialised as JSON. When a private function returns an error string (e.g. `"Namespace 'x' does not exist."`), the handler returns HTTP `400` with `{"detail": "<message>"}`.

## CORS

`CORSMiddleware` is added with `allow_origins=["*"]` so the UI can call from any origin during development. This can be tightened to a specific origin via an `CORS_ORIGINS` environment variable later.

## Launch

`main()` in `server.py` uses `asyncio.gather` to run both:

1. MCP via stdio — `mcp.run_async(transport="stdio")`
2. uvicorn on `0.0.0.0:8000` — port configurable via `HTTP_PORT` env var (default `8000`)

A single `python server.py` (or `uv run server.py`) starts both servers.

## Error Handling

| Condition                          | HTTP status |
|------------------------------------|-------------|
| Private function returns error str | `400`       |
| URL fetch fails inside index calls | `400`       |
| No namespace selected              | `400`       |
| Unhandled exception                | `500` (FastAPI default) |

The heuristic for detecting error strings: if the private function returns a `str` that is not a status message (checked by looking for keywords like `"does not exist"`, `"No namespace"`, `"Invalid name"`, `"Failed to"`), raise `HTTPException(400)`.

## Out of Scope

- Authentication / API keys
- Streaming progress for `index_tree` (long-running calls block until complete)
- Persistent namespace sessions across HTTP clients (current namespace is process-global, shared by all callers)
