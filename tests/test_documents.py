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
    path.write_text("Second version content here.", encoding="utf-8")
    server._index_file(ns, "test-ns", path)
    assert ns.count() > 0
    source_url = "file://test-ns/notes.txt"
    docs = ns.get(where={"source_url": source_url})
    assert all("Second" in d for d in docs["documents"])


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
    folder = tmp_uploads / "test-ns"
    folder.mkdir(exist_ok=True)
    path = _write(folder, "notes.txt", "Some content to index.")
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
