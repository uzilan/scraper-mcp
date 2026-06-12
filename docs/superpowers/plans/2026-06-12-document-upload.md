# Document Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to upload PDF, DOCX, XLSX, OpenAPI JSON/YAML, and plain text files into a namespace — stored on disk, indexed into ChromaDB for semantic search, and browsable in the sidebar.

**Architecture:** Files are saved to `data/uploads/{namespace}/` on disk. `_index_file()` in server.py extracts text by file type and passes it through the existing `chunk()` → `_upsert()` pipeline using `source_url = "file://{namespace}/{filename}"`. Four new router endpoints handle upload, list, serve, and delete. A new `DocumentsList` sidebar component sits between `NamespacePanel` and `PagesList`.

**Tech Stack:** Python (pypdf, python-docx, openpyxl, PyYAML), FastAPI (FileResponse, UploadFile), React + Vitest + React Testing Library.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `pyproject.toml` | Modify | Add pypdf, python-docx, openpyxl, PyYAML |
| `server.py` | Modify | Add UPLOADS_PATH, extraction fns, _index_file, _list_documents, _delete_document, MCP tool, update _delete_namespace |
| `router.py` | Modify | Add POST/GET/DELETE /documents and GET /documents/{filename} |
| `tests/conftest.py` | Modify | Add tmp_uploads fixture |
| `tests/test_documents.py` | Create | Backend unit tests |
| `ui/src/api.js` | Modify | Add uploadDocument, listDocuments, deleteDocument, getDocumentUrl |
| `ui/src/api.test.js` | Modify | Add tests for new api functions |
| `ui/src/hooks/useDocuments.js` | Create | Hook mirroring usePages.js |
| `ui/src/hooks/useDocuments.test.jsx` | Create | Hook tests |
| `ui/src/components/DocumentsList.jsx` | Create | Sidebar documents section |
| `ui/src/components/DocumentsList.test.jsx` | Create | Component tests |
| `ui/src/App.jsx` | Modify | Wire useDocuments + DocumentsList into sidebar |

---

## Task 1: Add Python Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dependencies to pyproject.toml**

In the `dependencies` list, add:
```toml
dependencies = [
    "beautifulsoup4>=4.14.3",
    "chromadb>=1.5.9",
    "fastapi>=0.115",
    "httpx>=0.28.1",
    "lxml>=6.1.1",
    "markdownify>=1.2.2",
    "mcp[cli]>=1.27.1",
    "openpyxl>=3.1",
    "pypdf>=5.0",
    "python-docx>=1.1",
    "python-multipart>=0.0.9",
    "PyYAML>=6.0",
    "tiktoken>=0.13.0",
    "uvicorn>=0.34",
]
```

Note: `python-multipart` is required by FastAPI for `UploadFile` support.

- [ ] **Step 2: Install dependencies**

```bash
uv sync
```

Expected: resolves and installs all packages with no errors.

- [ ] **Step 3: Verify imports work**

```bash
uv run python -c "from pypdf import PdfReader; from docx import Document; import openpyxl; import yaml; print('OK')"
```

Expected output: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add pypdf, python-docx, openpyxl, PyYAML, python-multipart"
```

---

## Task 2: Text Extraction Functions + `_index_file`

**Files:**
- Modify: `server.py`
- Create: `tests/test_documents.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add tmp_uploads fixture to conftest.py**

Add to `tests/conftest.py` (after the existing `reset_state` fixture):

```python
import server

@pytest.fixture
def tmp_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'UPLOADS_PATH', tmp_path)
    return tmp_path
```

- [ ] **Step 2: Write failing tests for extraction and indexing**

Create `tests/test_documents.py`:

```python
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import server


@pytest.fixture
def ns(tmp_uploads):
    server._create_namespace(server._chroma_client, "test-ns")
    server._use_namespace(server._chroma_client, "test-ns")
    return server._current_collection


def _write(tmp_path, name, content, mode="w"):
    path = tmp_path / name
    if mode == "wb":
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def test_index_file_txt(ns, tmp_uploads):
    path = _write(tmp_uploads, "readme.txt", "Hello world\n\nThis is documentation.")
    result = server._index_file(ns, "test-ns", path)
    assert "Indexed" in result
    assert "readme.txt" in result
    assert ns.count() > 0


def test_index_file_md(ns, tmp_uploads):
    path = _write(tmp_uploads, "guide.md", "# Guide\n\nThis is a guide.")
    result = server._index_file(ns, "test-ns", path)
    assert "Indexed" in result
    assert ns.count() > 0


def test_index_file_pdf(ns, tmp_uploads):
    path = tmp_uploads / "report.pdf"
    path.write_bytes(b"%PDF fake")
    with patch("server._extract_text_pdf", return_value="PDF content here"):
        result = server._index_file(ns, "test-ns", path)
    assert "Indexed" in result
    assert ns.count() > 0


def test_index_file_docx(ns, tmp_uploads):
    path = tmp_uploads / "doc.docx"
    path.write_bytes(b"PK fake docx")
    with patch("server._extract_text_docx", return_value="Docx content here"):
        result = server._index_file(ns, "test-ns", path)
    assert "Indexed" in result
    assert ns.count() > 0


def test_index_file_xlsx(ns, tmp_uploads):
    path = tmp_uploads / "sheet.xlsx"
    path.write_bytes(b"PK fake xlsx")
    with patch("server._extract_text_xlsx", return_value="Col A\tCol B\nVal 1\tVal 2"):
        result = server._index_file(ns, "test-ns", path)
    assert "Indexed" in result
    assert ns.count() > 0


def test_index_file_openapi_json(ns, tmp_uploads):
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test API"},
        "paths": {"/items": {"get": {"operationId": "listItems", "summary": "List items"}}},
    }
    path = _write(tmp_uploads, "api.json", json.dumps(spec))
    result = server._index_file(ns, "test-ns", path)
    assert "operations" in result
    assert ns.count() > 0


def test_index_file_openapi_yaml(ns, tmp_uploads):
    yaml_content = """
openapi: "3.0.0"
info:
  title: Test API
paths:
  /items:
    get:
      operationId: listItems
      summary: List items
"""
    path = _write(tmp_uploads, "api.yaml", yaml_content)
    result = server._index_file(ns, "test-ns", path)
    assert "operations" in result
    assert ns.count() > 0


def test_index_file_plain_json(ns, tmp_uploads):
    path = _write(tmp_uploads, "config.json", '{"key": "value"}')
    result = server._index_file(ns, "test-ns", path)
    assert "Indexed" in result
    assert ns.count() > 0


def test_index_file_unsupported_doc(ns, tmp_uploads):
    path = tmp_uploads / "old.doc"
    path.write_bytes(b"\xd0\xcf binary")
    result = server._index_file(ns, "test-ns", path)
    assert ".doc" in result
    assert "not supported" in result


def test_index_file_unknown_extension(ns, tmp_uploads):
    path = tmp_uploads / "file.xyz"
    path.write_bytes(b"data")
    result = server._index_file(ns, "test-ns", path)
    assert "Unsupported" in result


def test_index_file_overwrites_on_reupload(ns, tmp_uploads):
    path = _write(tmp_uploads, "notes.txt", "First version content here.")
    server._index_file(ns, "test-ns", path)
    count_first = ns.count()
    path.write_text("Second version content here.", encoding="utf-8")
    server._index_file(ns, "test-ns", path)
    # Should not grow unboundedly — old chunks deleted, new ones added
    assert ns.count() > 0
    source_url = "file://test-ns/notes.txt"
    docs = ns.get(where={"source_url": source_url})
    assert all("Second" in d for d in docs["documents"])
```

- [ ] **Step 3: Run to verify failure**

```bash
uv run pytest tests/test_documents.py -v
```

Expected: errors like `AttributeError: module 'server' has no attribute '_index_file'`

- [ ] **Step 4: Add UPLOADS_PATH and extraction functions to server.py**

Add after the `CHROMA_PATH` line:

```python
UPLOADS_PATH = Path(__file__).parent / "data" / "uploads"
```

Add after the `chunk()` function (before the OpenAPI helpers):

```python
def _extract_text_pdf(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_text_docx(path: Path) -> str:
    from docx import Document
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def _extract_text_xlsx(path: Path) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    lines = []
    for sheet in wb.worksheets:
        lines.append(f"# {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append("\t".join(cells))
    return "\n".join(lines)


def _index_file(collection: chromadb.Collection, namespace: str, path: Path) -> str:
    import yaml as _yaml
    source_url = f"file://{namespace}/{path.name}"
    suffix = path.suffix.lower()

    if suffix == ".doc":
        return f"Unsupported file type: .doc — convert to .docx first."

    if suffix in (".json", ".yaml", ".yml"):
        text = path.read_text(encoding="utf-8")
        data = json.loads(text) if suffix == ".json" else _yaml.safe_load(text)
        if isinstance(data, dict) and "paths" in data and ("openapi" in data or "swagger" in data):
            docs, ids, metas = _openapi_documents(data, source_url)
            ok = _upsert(collection, docs, ids, metas, source_url)
            return f"Indexed {len(docs)} operations from {path.name}" if ok else f"No content extracted from {path.name}"
        text_content = json.dumps(data, indent=2) if suffix == ".json" else text
    elif suffix == ".pdf":
        text_content = _extract_text_pdf(path)
    elif suffix == ".docx":
        text_content = _extract_text_docx(path)
    elif suffix == ".xlsx":
        text_content = _extract_text_xlsx(path)
    elif suffix in (".txt", ".md"):
        text_content = path.read_text(encoding="utf-8")
    else:
        return f"Unsupported file type: {suffix}"

    chunks_list = chunk(text_content)
    ids = [f"{source_url}::{i}" for i in range(len(chunks_list))]
    metas = [{"source_url": source_url} for _ in chunks_list]
    ok = _upsert(collection, chunks_list, ids, metas, source_url)
    return f"Indexed {len(chunks_list)} chunks from {path.name}" if ok else f"No content extracted from {path.name}"
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_documents.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/conftest.py tests/test_documents.py
git commit -m "feat: add file text extraction and _index_file to server.py"
```

---

## Task 3: `_list_documents` and `_delete_document`

**Files:**
- Modify: `server.py`
- Modify: `tests/test_documents.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_documents.py`:

```python
def test_list_documents_empty(tmp_uploads):
    result = server._list_documents("test-ns")
    assert result == []


def test_list_documents_with_files(tmp_uploads):
    folder = tmp_uploads / "test-ns"
    folder.mkdir()
    (folder / "guide.txt").write_text("hello", encoding="utf-8")
    (folder / "api.json").write_text("{}", encoding="utf-8")
    result = server._list_documents("test-ns")
    names = [d["name"] for d in result]
    assert "guide.txt" in names
    assert "api.json" in names
    assert all("size" in d and "content_type" in d for d in result)


def test_delete_document_removes_file_and_chromadb(ns, tmp_uploads):
    path = _write(tmp_uploads, "notes.txt", "Some content to index.")
    server._index_file(ns, "test-ns", path)
    assert ns.count() > 0
    assert path.exists()

    result = server._delete_document(ns, "test-ns", "notes.txt")
    assert "Deleted" in result
    assert not path.exists()
    source_url = "file://test-ns/notes.txt"
    assert ns.get(where={"source_url": source_url})["ids"] == []


def test_delete_document_not_found(ns, tmp_uploads):
    result = server._delete_document(ns, "test-ns", "ghost.txt")
    assert "not found" in result.lower()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_documents.py::test_list_documents_empty tests/test_documents.py::test_list_documents_with_files tests/test_documents.py::test_delete_document_removes_file_and_chromadb tests/test_documents.py::test_delete_document_not_found -v
```

Expected: `AttributeError: module 'server' has no attribute '_list_documents'`

- [ ] **Step 3: Add functions to server.py**

Add after `_index_file()`:

```python
def _list_documents(namespace: str) -> list[dict]:
    import mimetypes
    folder = UPLOADS_PATH / namespace
    if not folder.exists():
        return []
    return [
        {
            "name": f.name,
            "size": f.stat().st_size,
            "content_type": mimetypes.guess_type(f.name)[0] or "application/octet-stream",
        }
        for f in sorted(folder.iterdir())
        if f.is_file()
    ]


def _delete_document(collection: chromadb.Collection, namespace: str, filename: str) -> str:
    path = UPLOADS_PATH / namespace / filename
    source_url = f"file://{namespace}/{filename}"
    existing = collection.get(where={"source_url": source_url})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
    if path.exists():
        path.unlink()
        return f"Deleted {filename}"
    return f"File {filename} not found"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_documents.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_documents.py
git commit -m "feat: add _list_documents and _delete_document to server.py"
```

---

## Task 4: Namespace Deletion Cleans Up Uploads

**Files:**
- Modify: `server.py`
- Modify: `tests/test_documents.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_documents.py`:

```python
def test_delete_namespace_removes_uploads_folder(tmp_uploads):
    folder = tmp_uploads / "to-delete"
    folder.mkdir()
    (folder / "file.txt").write_text("content", encoding="utf-8")

    server._create_namespace(server._chroma_client, "to-delete")
    server._delete_namespace(server._chroma_client, "to-delete")

    assert not folder.exists()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_documents.py::test_delete_namespace_removes_uploads_folder -v
```

Expected: FAIL (folder still exists after delete).

- [ ] **Step 3: Update `_delete_namespace` in server.py**

Replace the existing `_delete_namespace` function:

```python
def _delete_namespace(client: chromadb.api.ClientAPI, name: str) -> str:
    import shutil
    global _current_collection
    try:
        client.delete_collection(name)
    except Exception:
        return f"Namespace '{name}' does not exist."
    if _current_collection is not None and _current_collection.name == name:
        _current_collection = None
    uploads_folder = UPLOADS_PATH / name
    if uploads_folder.exists():
        shutil.rmtree(uploads_folder)
    return f"Namespace '{name}' deleted."
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_documents.py tests/test_namespaces.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_documents.py
git commit -m "feat: delete namespace uploads folder when namespace is deleted"
```

---

## Task 5: MCP Tool `upload_document`

**Files:**
- Modify: `server.py`

No separate test — it is a thin wrapper around `_index_file` which is already tested.

- [ ] **Step 1: Add the MCP tool to server.py**

Add after the `clear_index` MCP tool (in the MCP tools section):

```python
@mcp.tool()
def upload_document(filename: str, content_b64: str) -> str:
    """Upload a document to the current namespace and index it for search. content_b64 must be base64-encoded file content."""
    import base64
    if _current_collection is None:
        return "No namespace selected. Call use_namespace(name) first."
    namespace = _current_collection.name
    folder = UPLOADS_PATH / namespace
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    path.write_bytes(base64.b64decode(content_b64))
    return _index_file(_current_collection, namespace, path)
```

- [ ] **Step 2: Run all backend tests to confirm no regressions**

```bash
uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "feat: add upload_document MCP tool"
```

---

## Task 6: Router Document Endpoints

**Files:**
- Modify: `router.py`
- Modify: `tests/test_router.py`

- [ ] **Step 1: Write failing router tests**

Append to `tests/test_router.py`:

```python
from pathlib import Path


@pytest.fixture
async def doc_client(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'UPLOADS_PATH', tmp_path)
    await client.post("/namespaces", json={"name": "doc-ns"})
    return client, tmp_path


async def test_upload_document_no_namespace(client):
    content = b"hello world document content"
    response = await client.post(
        "/documents",
        files={"file": ("test.txt", content, "text/plain")},
    )
    assert response.status_code == 400


async def test_upload_document_txt(doc_client):
    client, _ = doc_client
    content = b"This is documentation content for the test."
    response = await client.post(
        "/documents",
        files={"file": ("readme.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    assert "Indexed" in response.json()


async def test_list_documents_no_namespace(client):
    response = await client.get("/documents")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_documents_after_upload(doc_client):
    client, _ = doc_client
    content = b"Some content here for testing."
    await client.post("/documents", files={"file": ("notes.txt", content, "text/plain")})
    response = await client.get("/documents")
    assert response.status_code == 200
    docs = response.json()
    assert any(d["name"] == "notes.txt" for d in docs)


async def test_delete_document(doc_client):
    client, _ = doc_client
    content = b"Content to delete eventually."
    await client.post("/documents", files={"file": ("todelete.txt", content, "text/plain")})
    response = await client.delete("/documents/todelete.txt")
    assert response.status_code == 200
    assert "Deleted" in response.json()


async def test_serve_document(doc_client):
    client, _ = doc_client
    content = b"Serve this content back to the client."
    await client.post("/documents", files={"file": ("serve.txt", content, "text/plain")})
    response = await client.get("/documents/serve.txt")
    assert response.status_code == 200
    assert response.content == content


async def test_serve_document_not_found(doc_client):
    client, _ = doc_client
    response = await client.get("/documents/ghost.txt")
    assert response.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_router.py::test_upload_document_no_namespace -v
```

Expected: FAIL with 404 (route doesn't exist yet).

- [ ] **Step 3: Add endpoints to router.py**

Add these imports at the top of `router.py`:

```python
from fastapi import File, UploadFile
from fastapi.responses import FileResponse
```

Add the four endpoints after the `clear_index_route` endpoint:

```python
@app.post("/documents")
async def upload_document_route(file: UploadFile = File(...)) -> str:
    if server._current_collection is None:
        raise HTTPException(status_code=400, detail="No namespace selected. Call use_namespace first.")
    namespace = server._current_collection.name
    folder = server.UPLOADS_PATH / namespace
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / file.filename
    path.write_bytes(await file.read())
    result = server._index_file(server._current_collection, namespace, path)
    if "not supported" in result.lower() or result.startswith("Unsupported") or "No content extracted" in result:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.get("/documents")
def list_documents_route() -> list[dict]:
    if server._current_collection is None:
        return []
    return server._list_documents(server._current_collection.name)


@app.delete("/documents/{filename}")
def delete_document_route(filename: str) -> str:
    if server._current_collection is None:
        raise HTTPException(status_code=400, detail="No namespace selected. Call use_namespace first.")
    return server._delete_document(server._current_collection, server._current_collection.name, filename)


@app.get("/documents/{filename}")
def serve_document_route(filename: str):
    if server._current_collection is None:
        raise HTTPException(status_code=400, detail="No namespace selected. Call use_namespace first.")
    path = server.UPLOADS_PATH / server._current_collection.name / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    return FileResponse(path)
```

- [ ] **Step 4: Run router tests**

```bash
uv run pytest tests/test_router.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add router.py tests/test_router.py
git commit -m "feat: add document upload/list/delete/serve endpoints to router"
```

---

## Task 7: `api.js` Document Functions

**Files:**
- Modify: `ui/src/api.js`
- Modify: `ui/src/api.test.js`

- [ ] **Step 1: Add new imports to the existing import block at the top of api.test.js**

The file starts with:
```javascript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  listNamespaces, currentNamespace, ...
} from './api'
```

Add `uploadDocument, listDocuments, deleteDocument, getDocumentUrl` to the existing `./api` import list. Do NOT add a second import line.

- [ ] **Step 2: Write failing tests**

Append to `ui/src/api.test.js` (after all existing `describe` blocks). The file uses `mockFetch`/`mockOk` helpers already defined at the top:

```javascript
describe('uploadDocument', () => {
  it('POSTs FormData to /documents', async () => {
    mockOk('Indexed 2 chunks from report.txt')
    const file = new File(['hello'], 'report.txt', { type: 'text/plain' })
    const result = await uploadDocument(file)
    expect(result).toContain('Indexed')
    expect(mockFetch).toHaveBeenCalledWith('/documents', expect.objectContaining({ method: 'POST' }))
    const body = mockFetch.mock.calls[0][1].body
    expect(body).toBeInstanceOf(FormData)
  })
})

describe('listDocuments', () => {
  it('GETs /documents and returns array', async () => {
    mockOk([{ name: 'guide.pdf', size: 1234, content_type: 'application/pdf' }])
    const result = await listDocuments()
    expect(mockFetch).toHaveBeenCalledWith('/documents', undefined)
    expect(result[0].name).toBe('guide.pdf')
  })
})

describe('deleteDocument', () => {
  it('DELETEs /documents/{name}', async () => {
    mockOk('Deleted guide.pdf')
    await deleteDocument('guide.pdf')
    expect(mockFetch).toHaveBeenCalledWith(
      '/documents/guide.pdf',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})

describe('getDocumentUrl', () => {
  it('returns encoded path', () => {
    expect(getDocumentUrl('my file.pdf')).toBe('/documents/my%20file.pdf')
    expect(getDocumentUrl('api.json')).toBe('/documents/api.json')
  })
})
```

- [ ] **Step 3: Run to verify failure**

```bash
cd ui && npx vitest run src/api.test.js
```

Expected: FAIL with import errors for the new functions.

- [ ] **Step 4: Add functions to api.js**

Append to `ui/src/api.js`:

```javascript
export function uploadDocument(file) {
  const form = new FormData()
  form.append('file', file)
  return _fetch('/documents', { method: 'POST', body: form })
}

export function listDocuments() {
  return _fetch('/documents')
}

export function deleteDocument(name) {
  return _fetch(`/documents/${encodeURIComponent(name)}`, { method: 'DELETE', headers: JSON_HEADERS })
}

export function getDocumentUrl(name) {
  return `/documents/${encodeURIComponent(name)}`
}
```

- [ ] **Step 5: Run tests**

```bash
cd ui && npx vitest run src/api.test.js
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add ui/src/api.js ui/src/api.test.js
git commit -m "feat: add document api functions"
```

---

## Task 8: `useDocuments` Hook

**Files:**
- Create: `ui/src/hooks/useDocuments.js`
- Create: `ui/src/hooks/useDocuments.test.jsx`

- [ ] **Step 1: Write failing tests**

Create `ui/src/hooks/useDocuments.test.jsx`:

```javascript
import { renderHook, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { useDocuments } from './useDocuments'
import * as api from '../api'

vi.mock('../api')

describe('useDocuments', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches documents when current namespace is set', async () => {
    api.listDocuments.mockResolvedValue([{ name: 'guide.pdf', size: 1024, content_type: 'application/pdf' }])
    const { result } = renderHook(() => useDocuments('my-ns'))
    await waitFor(() => expect(result.current.documents).toHaveLength(1))
    expect(result.current.documents[0].name).toBe('guide.pdf')
  })

  it('returns empty documents when current is null', async () => {
    const { result } = renderHook(() => useDocuments(null))
    await waitFor(() => expect(result.current.documents).toEqual([]))
    expect(api.listDocuments).not.toHaveBeenCalled()
  })

  it('refetches when current namespace changes', async () => {
    api.listDocuments
      .mockResolvedValueOnce([{ name: 'a.pdf', size: 100, content_type: 'application/pdf' }])
      .mockResolvedValueOnce([{ name: 'b.txt', size: 200, content_type: 'text/plain' }])

    const { result, rerender } = renderHook(({ ns }) => useDocuments(ns), { initialProps: { ns: 'ns1' } })
    await waitFor(() => expect(result.current.documents[0].name).toBe('a.pdf'))

    rerender({ ns: 'ns2' })
    await waitFor(() => expect(result.current.documents[0].name).toBe('b.txt'))
  })

  it('exposes a refresh function', async () => {
    api.listDocuments.mockResolvedValue([])
    const { result } = renderHook(() => useDocuments('my-ns'))
    await waitFor(() => expect(result.current.documents).toEqual([]))
    expect(typeof result.current.refresh).toBe('function')
  })
})
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ui && npx vitest run src/hooks/useDocuments.test.jsx
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create useDocuments.js**

Create `ui/src/hooks/useDocuments.js`:

```javascript
import { useState, useEffect, useCallback } from 'react'
import { listDocuments } from '../api'

export function useDocuments(current) {
  const [documents, setDocuments] = useState([])

  const refresh = useCallback(async () => {
    if (!current) { setDocuments([]); return }
    try {
      const result = await listDocuments()
      setDocuments(result)
    } catch {
      setDocuments([])
    }
  }, [current])

  useEffect(() => { refresh() }, [refresh])

  return { documents, refresh }
}
```

- [ ] **Step 4: Run tests**

```bash
cd ui && npx vitest run src/hooks/useDocuments.test.jsx
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add ui/src/hooks/useDocuments.js ui/src/hooks/useDocuments.test.jsx
git commit -m "feat: add useDocuments hook"
```

---

## Task 9: `DocumentsList` Component

**Files:**
- Create: `ui/src/components/DocumentsList.jsx`
- Create: `ui/src/components/DocumentsList.test.jsx`

- [ ] **Step 1: Write failing tests**

Create `ui/src/components/DocumentsList.test.jsx`:

```javascript
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect } from 'vitest'
import DocumentsList from './DocumentsList'

const docs = [
  { name: 'guide.pdf', size: 2048, content_type: 'application/pdf' },
  { name: 'sheet.xlsx', size: 1024, content_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
  { name: 'readme.txt', size: 512, content_type: 'text/plain' },
]

describe('DocumentsList', () => {
  it('renders document count in header', () => {
    render(<DocumentsList documents={docs} onUpload={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText('(3)')).toBeInTheDocument()
  })

  it('renders empty list without error', () => {
    render(<DocumentsList documents={[]} onUpload={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText('(0)')).toBeInTheDocument()
  })

  it('renders each document name', () => {
    render(<DocumentsList documents={docs} onUpload={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText(/guide\.pdf/)).toBeInTheDocument()
    expect(screen.getByText(/sheet\.xlsx/)).toBeInTheDocument()
    expect(screen.getByText(/readme\.txt/)).toBeInTheDocument()
  })

  it('PDF opens in new tab (target _blank, no download attr)', () => {
    render(<DocumentsList documents={[docs[0]]} onUpload={vi.fn()} onDelete={vi.fn()} />)
    const link = screen.getByRole('link', { name: /guide\.pdf/ })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).not.toHaveAttribute('download')
  })

  it('xlsx forces download (download attr, no target _blank)', () => {
    render(<DocumentsList documents={[docs[1]]} onUpload={vi.fn()} onDelete={vi.fn()} />)
    const link = screen.getByRole('link', { name: /sheet\.xlsx/ })
    expect(link).toHaveAttribute('download')
    expect(link).not.toHaveAttribute('target', '_blank')
  })

  it('txt opens in new tab', () => {
    render(<DocumentsList documents={[docs[2]]} onUpload={vi.fn()} onDelete={vi.fn()} />)
    const link = screen.getByRole('link', { name: /readme\.txt/ })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).not.toHaveAttribute('download')
  })

  it('calls onDelete with filename when delete button clicked', async () => {
    const onDelete = vi.fn()
    render(<DocumentsList documents={[docs[0]]} onUpload={vi.fn()} onDelete={onDelete} />)
    await userEvent.click(screen.getByRole('button', { name: /delete guide\.pdf/i }))
    expect(onDelete).toHaveBeenCalledWith('guide.pdf')
  })

  it('calls onUpload when file selected', async () => {
    const onUpload = vi.fn()
    render(<DocumentsList documents={[]} onUpload={onUpload} onDelete={vi.fn()} />)
    const input = document.querySelector('input[type="file"]')
    const file = new File(['content'], 'new.txt', { type: 'text/plain' })
    await userEvent.upload(input, file)
    expect(onUpload).toHaveBeenCalledWith(file)
  })
})
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ui && npx vitest run src/components/DocumentsList.test.jsx
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create DocumentsList.jsx**

Create `ui/src/components/DocumentsList.jsx`:

```jsx
import { useRef, useState } from 'react'

const OPEN_IN_BROWSER = new Set(['.pdf', '.txt', '.md', '.json', '.yaml', '.yml'])

function getExt(name) {
  const idx = name.lastIndexOf('.')
  return idx >= 0 ? name.slice(idx).toLowerCase() : ''
}

function fileIcon(name) {
  const ext = getExt(name)
  if (ext === '.pdf') return '📄'
  if (ext === '.docx') return '📝'
  if (ext === '.xlsx') return '📊'
  if (ext === '.json' || ext === '.yaml' || ext === '.yml') return '⚙️'
  return '📃'
}

export default function DocumentsList({ documents, onUpload, onDelete }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const handleFiles = (files) => {
    for (const file of files) onUpload(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFiles([...e.dataTransfer.files])
  }

  return (
    <div
      className={`flex flex-col p-3.5 border-b border-slate-800${dragging ? ' bg-slate-800' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="text-[10px] uppercase tracking-widest text-slate-600">
          Documents <span className="text-slate-700 ml-1">({documents.length})</span>
        </div>
        <button
          onClick={() => inputRef.current?.click()}
          className="text-[10px] text-slate-500 hover:text-sky-400 px-1 leading-none"
          title="Upload document"
        >
          +
        </button>
      </div>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".pdf,.docx,.xlsx,.json,.yaml,.yml,.txt,.md"
        multiple
        onChange={(e) => handleFiles([...e.target.files])}
      />
      <div className="flex flex-col gap-0.5">
        {documents.map((doc) => {
          const ext = getExt(doc.name)
          const url = `/documents/${encodeURIComponent(doc.name)}`
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
              <button
                onClick={() => onDelete(doc.name)}
                aria-label={`Delete ${doc.name}`}
                className="text-slate-700 hover:text-red-400 text-[10px] opacity-0 group-hover:opacity-100"
              >
                ×
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests**

```bash
cd ui && npx vitest run src/components/DocumentsList.test.jsx
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/DocumentsList.jsx ui/src/components/DocumentsList.test.jsx
git commit -m "feat: add DocumentsList component"
```

---

## Task 10: Wire `App.jsx`

**Files:**
- Modify: `ui/src/App.jsx`

No new tests — integration is thin wiring; existing component and hook tests cover the logic.

- [ ] **Step 1: Update App.jsx**

Add import at the top:
```jsx
import DocumentsList from './components/DocumentsList'
import { useDocuments } from './hooks/useDocuments'
```

Add hook call after `usePages`:
```jsx
const { documents, refresh: refreshDocuments } = useDocuments(current)
```

In the sidebar JSX, add `<DocumentsList>` between `<NamespacePanel>` and `<PagesList>`:
```jsx
<NamespacePanel
  namespaces={namespaces}
  current={current}
  onCreate={create}
  onSwitch={switchTo}
  onDelete={remove}
/>
<DocumentsList
  documents={documents}
  onUpload={async (file) => {
    try {
      await api.uploadDocument(file)
      refreshDocuments()
    } catch {
      // silent — file may be unsupported
    }
  }}
  onDelete={async (name) => {
    try {
      await api.deleteDocument(name)
      refreshDocuments()
    } catch {
      // silent
    }
  }}
/>
<PagesList pages={pages} />
```

- [ ] **Step 2: Run all frontend tests**

```bash
cd ui && npx vitest run
```

Expected: all pass.

- [ ] **Step 3: Run backend tests**

```bash
uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add ui/src/App.jsx
git commit -m "feat: wire DocumentsList into App sidebar"
```

---

## Task 11: Manual Verification

- [ ] **Step 1: Build the UI and start the server**

```bash
cd ui && npm run build && cd .. && uv run python server.py
```

- [ ] **Step 2: Open the app**

Navigate to `http://localhost:8000/ui`

- [ ] **Step 3: Verify upload flow**

1. Create or select a namespace
2. Click `+` in the Documents section (between namespace panel and pages)
3. Select a `.txt` file — confirm it appears in the list
4. Click the document link — confirm it opens in a new browser tab
5. Upload a `.docx` file — confirm it appears
6. Click `.docx` link — confirm it downloads (not opens)
7. Run a search — confirm uploaded content appears in results

- [ ] **Step 4: Verify delete flow**

1. Hover a document — confirm `×` appears
2. Click `×` — confirm document removed from list
3. Search for content from that document — confirm no results

- [ ] **Step 5: Verify drag-and-drop**

Drag a file onto the Documents section — confirm it uploads and appears.
