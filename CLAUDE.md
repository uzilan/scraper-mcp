# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (Python)

```bash
# Run the server (MCP stdio + HTTP on port 8000, concurrently)
uv run python server.py

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_router.py

# Run a single test
uv run pytest tests/test_router.py::test_function_name
```

### Frontend (React)

```bash
cd ui

# Dev server (proxies API to localhost:8000)
npm run dev

# Build for production (output to ui/dist/)
npm run build

# Run tests
npm test

# Run a single test file
npx vitest run src/components/NamespacePanel.test.jsx
```

## Architecture

The system has two parallel interfaces over a shared in-process state:

**`server.py`** — MCP server (FastMCP) that defines all tools (`create_namespace`, `index_page`, `search_docs`, etc.) and contains all business logic. Also the entry point: `main()` runs MCP (stdio) and the FastAPI HTTP server concurrently via `asyncio.gather`.

**`router.py`** — FastAPI REST layer that exposes the same capabilities over HTTP. It calls `server.py`'s private `_*` functions directly (not via MCP). On startup, it initializes `server._chroma_client` if MCP lifespan hasn't run (supporting standalone HTTP mode). Serves the built UI from `ui/dist/` at `/ui`.

**`ui/`** — React + Vite + Tailwind frontend. `api.js` is the sole HTTP client layer. Dev server proxies all API paths (`/namespaces`, `/index`, `/search`, `/links`) to `localhost:8000`.

### Shared state

Both MCP and HTTP share two module-level globals in `server.py`:
- `_chroma_client` — the ChromaDB persistent client (path: `data/chroma/`)
- `_current_collection` — the active namespace (a ChromaDB collection). Setting a namespace is session-global, not per-request.

A **namespace** is a ChromaDB collection. Namespace operations must precede indexing or search.

### Indexing pipeline

HTML pages: fetch → strip nav/footer/scripts → markdownify → chunk by token count (500 tokens, cl100k_base tokenizer) → upsert into ChromaDB.

OpenAPI/Swagger: detected by JSON content-type + `paths` key. Each HTTP operation becomes one document. Swagger UI pages are also detected and their spec URLs resolved automatically.

Streaming endpoints (`/index/tree/stream`, `/links/stream`) use SSE via an `asyncio.Queue` bridging the crawl coroutine to the HTTP response generator.

### Testing

Backend tests use `chromadb.EphemeralClient()` (in-memory). The `conftest.py` `reset_state` fixture (autouse) replaces `server._chroma_client` with a fresh ephemeral client before each test and clears `_current_collection`.

Frontend tests use Vitest + jsdom + React Testing Library. `src/test/setup.js` configures jest-dom matchers. `api.js` is mocked at the module level in component tests.
