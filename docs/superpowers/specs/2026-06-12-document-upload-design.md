# Document Upload Feature — Design Spec

**Date:** 2026-06-12
**Status:** Approved

## Summary

Allow users to upload files (PDF, DOCX, XLSX, OpenAPI JSON/YAML, plain text) into a namespace. Uploaded files are stored on disk, indexed into ChromaDB for semantic search alongside web pages, and displayed in the sidebar for viewing or downloading.

---

## Architecture & Data Flow

```
UI upload → POST /documents (multipart/form-data)
  → router saves file to data/uploads/{namespace}/{filename}
  → calls server._index_file(collection, namespace, path)
    → extract text by file suffix
    → chunk() → _upsert() into ChromaDB
      source_url = "file://{namespace}/{filename}"
  → returns chunk count

GET /documents      → lists files in data/uploads/{namespace}/
GET /documents/{filename} → serves raw file (FileResponse)
DELETE /documents/{filename} → removes file + ChromaDB docs for that source_url
```

Files are namespaced: `data/uploads/{namespace}/`. The folder is created on first upload. Deleting a namespace also deletes its uploads folder.

---

## Backend — `server.py`

**New constants:**
- `UPLOADS_PATH = Path(__file__).parent / "data" / "uploads"`

**New private functions:**
- `_index_file(collection, namespace, path) -> str` — reads file, dispatches to extractor by suffix, calls `chunk()` + `_upsert()` with `source_url = f"file://{namespace}/{path.name}"`
- `_list_documents(namespace) -> list[dict]` — scans `UPLOADS_PATH / namespace`, returns `[{name, size, content_type}]`
- `_delete_document(collection, namespace, filename)` — deletes file from disk + removes ChromaDB docs for that source_url

**New MCP tool:**
- `upload_document(filename: str, content_b64: str) -> str` — accepts base64-encoded file content; saves to disk and indexes. Enables Claude to upload documents directly.

**Text extractors (by file suffix):**

| Extension | Library | Strategy |
|-----------|---------|----------|
| `.pdf` | `pypdf` | extract text per page, join |
| `.docx` | `python-docx` | join paragraph texts |
| `.xlsx` | `openpyxl` | join cell values per row, per sheet |
| `.json` / `.yaml` / `.yml` | stdlib + `PyYAML` | if OpenAPI spec (`paths` key), use existing `_openapi_documents()`; else serialize as text |
| `.txt` / `.md` | built-in | read directly |
| `.doc` | — | not supported (binary format); return clear error message |

All extracted text passes through the existing `chunk()` → `_upsert()` pipeline unchanged.

---

## Backend — `router.py`

Four new endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/documents` | `multipart/form-data` upload; saves file + indexes |
| `GET` | `/documents` | lists documents in current namespace |
| `DELETE` | `/documents/{filename}` | removes file + ChromaDB docs |
| `GET` | `/documents/{filename}` | serves raw file via `FileResponse` |

All document endpoints require an active namespace (return 400 if none selected).

---

## Frontend

### `useDocuments.js` hook
Mirrors `usePages.js`. Fetches document list when namespace changes. Exposes `{ documents, refresh }`.

### `DocumentsList` component
Placed in sidebar **between** `NamespacePanel` and `PagesList`.

- Section header: `DOCUMENTS (n)` — matches existing `INDEXED PAGES` style
- Upload trigger: click-to-open file picker (filtered to accepted types) or drag-and-drop onto the section
- Each document row: file type icon + filename + `×` delete button
- Click behavior:
  - PDF, txt, md, json, yaml → `window.open(url, '_blank')` (browser can render)
  - docx, xlsx → `<a href={url} download>` (force download)
- Delete: calls `deleteDocument(name)`, then `refresh()`

### `api.js` additions
- `uploadDocument(file)` — `POST /documents` with `FormData`
- `listDocuments()` — `GET /documents`
- `deleteDocument(name)` — `DELETE /documents/{name}`
- `getDocumentUrl(name)` — returns `/documents/{name}` (used as href/src)

### `App.jsx` changes
- Add `useDocuments(current)` hook call alongside existing `usePages(current)`
- Pass `documents` + `refreshDocuments` to `DocumentsList`
- `refreshDocuments()` called after successful upload or delete

---

## Dependencies

New Python packages to add to `pyproject.toml`:
- `pypdf`
- `python-docx`
- `openpyxl`
- `PyYAML`

---

## Out of Scope

- `.doc` (old binary Word format) — not supported, returns error
- Re-indexing a file after upload (upload always re-indexes)
- Uploading the same filename twice overwrites the previous file and re-indexes
