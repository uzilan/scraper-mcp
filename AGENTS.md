# AGENTS.md

This file provides guidance for coding agents and contributors working in this repository, regardless of the tools they use.

## Working Guidelines

- State important assumptions and ask for clarification when ambiguity affects the implementation. Do not invent API details or configuration options that cannot be verified.
- Make the smallest change that solves the requested problem. Avoid speculative features, unnecessary abstractions, and unrelated refactoring or formatting.
- Follow the existing language, framework, naming, and testing conventions. Preserve unrelated changes and remove only unused code introduced by your own work.
- For multi-step tasks, outline a brief plan with verifiable success criteria before editing. Update documentation when the requested change affects usage or behavior.
- Validate changes with the most relevant tests or checks first, then broader checks as needed. Report what was verified and any limitations; do not claim checks passed unless they ran successfully.
- Keep credentials and sensitive data out of code, logs, and responses. Do not commit, create branches, or perform destructive operations unless requested.
- Keep progress updates and final summaries concise, focusing on changes, verification, and unresolved issues.

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

**`server.py`** — Application entry point and startup wiring. `main()` starts MCP (stdio) and the FastAPI HTTP server concurrently, or MCP alone when `MCP_ONLY` is set.

**`mcp_tools.py`** — FastMCP instance, MCP lifespan, and decorated tool wrappers delegating to the shared application functions.

**`router.py`** — FastAPI REST layer that exposes the same capabilities over HTTP without importing the MCP entry point. Serves the built UI from `ui/dist/` at `/ui`.

**`application.py`** — Shared application functions used by both interfaces, including active-namespace checks and document upload orchestration.

**`namespaces.py`** — Namespace management, shared ChromaDB state, storage paths, and idempotent client initialization used by both lifespans (including standalone HTTP mode).

**`indexing.py`** — Page/tree indexing, ChromaDB writes, indexed-page listing, and index clearing.

**`crawling.py`** — HTTP fetching and HTML/Markdown link discovery.

**`parsing.py`**, **`openapi.py`**, **`documents.py`** — HTML parsing/token chunking, OpenAPI/Swagger extraction, and uploaded-file extraction/indexing respectively.

**`search.py`** — Search result ranking and agent-backed answers. **`agent.py`** dispatches requests using `AGENT_PROVIDER` (`claude` by default, or `codex`). **`claude_agent.py`** manages the reusable Claude SDK client; **`codex_agent.py`** runs isolated non-interactive local Codex CLI requests and cleans up subprocesses on cancellation. The browser and MCP interfaces share the same provider setting and response format.

**`ui/`** — React + Vite + Tailwind frontend. `api.js` is the sole HTTP client layer. Dev server proxies all API paths (`/namespaces`, `/index`, `/search`, `/links`) to `localhost:8000`.

### Shared state

Both MCP and HTTP share two module-level globals in `namespaces.py`:
- `chroma_client` — the ChromaDB persistent client (path: `data/chroma/`)
- `current_collection` — the active namespace (a ChromaDB collection). Setting a namespace is session-global, not per-request.

A **namespace** is a ChromaDB collection. Namespace operations must precede indexing or search.

### Indexing pipeline

HTML pages: fetch → strip nav/footer/scripts → markdownify → chunk by token count (500 tokens, cl100k_base tokenizer) → upsert into ChromaDB.

OpenAPI/Swagger: detected by JSON content-type + `paths` key. Each HTTP operation becomes one document. Swagger UI pages are also detected and their spec URLs resolved automatically.

Streaming endpoints (`/index/tree/stream`, `/links/stream`) use SSE via an `asyncio.Queue` bridging the crawl coroutine to the HTTP response generator.

### Testing

Backend tests use `chromadb.EphemeralClient()` (in-memory). The `conftest.py` `reset_state` fixture (autouse) replaces `namespaces.chroma_client` with a fresh ephemeral client before each test and clears `current_collection`. Tests patch dependencies in their owning modules (for example, `crawling.fetch` and `search.ask_agent`). Application integration tests verify MCP/HTTP shared state and the MCP tool contract.

Frontend tests use Vitest + jsdom + React Testing Library. `src/test/setup.js` configures jest-dom matchers. `api.js` is mocked at the module level in component tests.
