# Swagger UI Wrapper

**Date:** 2026-06-18
**Status:** Approved

## Goal

Render OpenAPI/Swagger specs in Swagger UI instead of raw JSON/YAML, for both uploaded documents and indexed external URLs.

## Backend Changes

### New route: `GET /swagger-ui?url=<spec>`

Serves a minimal inline HTML page that loads Swagger UI from CDN and initialises it with the provided `url`. No template file — the HTML is an inline string in `router.py`. Returns 400 if `url` param is missing.

### New route: `GET /proxy/spec?url=<external>`

Fetches the external spec URL server-side via httpx and returns the content with its original content-type (JSON or YAML). Avoids browser CORS restrictions. Returns 502 if the upstream fetch fails.

### Metadata change: `is_openapi` flag

When `_index_response` or `upload_document` detects an OpenAPI spec, every metadata dict stored in ChromaDB gains `"is_openapi": True`. `_list_indexed_pages` propagates this flag in its return value so the frontend can act on it.

Affects:
- `_openapi_documents` — already called for both URL-indexed and file-uploaded specs
- `_list_indexed_pages` — reads metadata, adds `is_openapi` to returned dicts

## Frontend Changes

### `DocumentsList`

For files with extension `.json`, `.yaml`, or `.yml`: change the link `href` from `getDocumentUrl(doc.name)` to `/swagger-ui?url=/documents/{doc.name}`. No other changes. Still opens in a new tab.

No client-side detection of whether the file is actually an OpenAPI spec — the user chose to upload it.

### `PagesList`

If `page.is_openapi` is true: change the link `href` to `/swagger-ui?url=/proxy/spec?url=${encodeURIComponent(page.url)}`. Add a small visual indicator (e.g. `[API]` label or distinct icon) to distinguish OpenAPI pages from regular pages.

## Data Flow

```
Upload swagger.json
  → DocumentsList → /swagger-ui?url=/documents/swagger.json
  → Swagger UI fetches /documents/swagger.json  (same-origin, no CORS)

Index https://api.example.com/openapi.json
  → stored with is_openapi:true
  → PagesList → /swagger-ui?url=/proxy/spec?url=https://api.example.com/openapi.json
  → Swagger UI fetches /proxy/spec  (same-origin, no CORS)
  → backend fetches external URL server-side  (no CORS restriction)
```

## What Does Not Change

- ChromaDB indexing and search logic
- Upload pipeline and file storage
- All existing routes
- npm dependencies (zero new packages)
