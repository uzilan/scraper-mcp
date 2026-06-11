# Scraper MCP — Design Spec

**Date:** 2026-06-10

## Overview

A new standalone MCP server inspired by lumanator. Scrapes and indexes documentation pages from arbitrary URLs into isolated namespaces, then enables semantic search scoped to a namespace. Data across namespaces never mixes.

## Architecture

- **Stack:** FastMCP, ChromaDB, httpx, BeautifulSoup, markdownify, tiktoken — same as lumanator
- **Storage:** Single `PersistentClient` at `data/chroma/` (relative to `server.py`). Each namespace maps to one ChromaDB collection inside that client.
- **Session state:** One `current_collection: chromadb.Collection | None` variable. Starts as `None`. Set by `use_namespace`. Resets on server restart.
- **No CLI args** — namespace lifecycle managed entirely through MCP tools.

## Tools

### Namespace Management

| Tool | Signature | Behavior |
|------|-----------|----------|
| `create_namespace` | `(name: str)` | Creates collection if not exists (idempotent). Does not switch active namespace. Validates name: 3–63 chars, alphanumeric + hyphens/underscores only (ChromaDB constraint). |
| `delete_namespace` | `(name: str)` | Deletes collection + all data. If it was the active namespace, clears session state. |
| `list_namespaces` | `()` | Returns list of all existing namespace names. |
| `use_namespace` | `(name: str)` | Sets active namespace. Errors if name doesn't exist. |
| `current_namespace` | `()` | Returns active namespace name, or `"No namespace selected"`. |

### Indexing & Search

All tools below require an active namespace. Return an error string if none is set.

| Tool | Signature | Behavior |
|------|-----------|----------|
| `index_page` | `(url: str)` | Fetch one page, detect OpenAPI or HTML, upsert into current namespace. |
| `index_tree` | `(url: str, max_depth: int = 2, force: bool = False)` | BFS crawl from URL, same-domain only, index each page. |
| `discover_links` | `(url: str, max_depth: int = 2)` | BFS crawl, return URLs without indexing. No active namespace required. |
| `list_indexed_pages` | `()` | List all indexed URLs + chunk counts in current namespace. |
| `clear_index` | `()` | Delete all documents from current namespace only. |
| `search_docs` | `(query: str, n_results: int = 5)` | Semantic search within current namespace only. |

## Data Flow

Identical to lumanator:

- **HTML:** `httpx.get` → BeautifulSoup (strip nav/footer/script/style/header) → markdownify → tiktoken chunker (500 token max) → `collection.add`
- **OpenAPI:** detected by `"paths"` + `"openapi"|"swagger"` keys in JSON → each `{method, path}` operation = one document
- **Swagger UI auto-discovery:** same `_extract_swagger_ui_links` + `_resolve_swagger_spec_urls` logic as lumanator
- **Re-indexing:** deletes old chunks by `source_url` before inserting new ones

## Error Handling

| Situation | Response |
|-----------|----------|
| Tool requires namespace, none active | `"No namespace selected. Call use_namespace(name) first."` |
| `use_namespace` with non-existent name | `"Namespace 'X' does not exist. Call create_namespace('X') first."` |
| `create_namespace` on existing name | Succeeds silently (idempotent) |
| `delete_namespace` on non-existent name | Returns clear error string |
| Fetch failure during crawl | Log warning, continue BFS (same as lumanator) |

## What's Shared With Lumanator

All helper functions are identical and can be copied directly:
- `extract_links`, `parse`, `chunk`
- `_openapi_documents`, `_resolve_swagger_spec_urls`, `_extract_swagger_ui_links`
- `_is_openapi`, `_fetch`, `_is_indexed`, `_upsert`, `_index_response`, `_enqueue_links`

The only structural difference: lumanator picks its collection at startup via CLI arg; this server manages collections dynamically through tools.
