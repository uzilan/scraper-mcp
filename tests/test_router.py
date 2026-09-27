import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import agent
import httpx
import pytest
import server
from router import _lifespan, app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_create_namespace(client):
    response = await client.post("/namespaces", json={"name": "my-ns"})
    assert response.status_code == 200
    assert "my-ns" in response.json()


async def test_create_namespace_invalid_name(client):
    response = await client.post("/namespaces", json={"name": "x"})
    assert response.status_code == 400


async def test_list_namespaces_empty(client):
    response = await client.get("/namespaces")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_namespaces_after_create(client):
    await client.post("/namespaces", json={"name": "ns-a"})
    await client.post("/namespaces", json={"name": "ns-b"})
    response = await client.get("/namespaces")
    assert "ns-a" in response.json()
    assert "ns-b" in response.json()


async def test_delete_namespace(client):
    await client.post("/namespaces", json={"name": "to-delete"})
    response = await client.delete("/namespaces/to-delete")
    assert response.status_code == 200
    assert "deleted" in response.json().lower()


async def test_delete_namespace_not_found(client):
    response = await client.delete("/namespaces/ghost")
    assert response.status_code == 400


async def test_use_namespace(client):
    await client.post("/namespaces", json={"name": "switch-to"})
    # create a second namespace so current_namespace changes
    await client.post("/namespaces", json={"name": "other"})
    response = await client.post("/namespaces/switch-to/use")
    assert response.status_code == 200
    assert "switch-to" in response.json()


async def test_use_namespace_not_found(client):
    response = await client.post("/namespaces/ghost/use")
    assert response.status_code == 400


async def test_current_namespace_none(client):
    response = await client.get("/namespaces/current")
    assert response.status_code == 200
    assert response.json() == ""


async def test_current_namespace_set(client):
    await client.post("/namespaces", json={"name": "active"})
    response = await client.get("/namespaces/current")
    assert response.status_code == 200
    assert response.json() == "active"


def _html_response(body: str) -> MagicMock:
    resp = MagicMock()
    resp.text = body
    resp.headers = {"content-type": "text/html"}
    resp.json.side_effect = Exception("not json")
    return resp


SIMPLE_HTML = "<html><body><h1>Hello</h1><p>Some documentation content here.</p></body></html>"


@pytest.fixture
async def ns_client(client):
    await client.post("/namespaces", json={"name": "test-ns"})
    return client


async def test_index_page_no_namespace(client):
    response = await client.post("/index/page", json={"url": "http://example.com"})
    assert response.status_code == 400


async def test_index_page_success(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        response = await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    assert response.status_code == 200
    assert "Indexed" in response.json()


async def test_index_page_fetch_failure(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=None)):
        response = await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    assert response.status_code == 400


async def test_index_tree_no_namespace(client):
    response = await client.post("/index/tree", json={"url": "http://example.com"})
    assert response.status_code == 400


async def test_index_tree_success(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        response = await ns_client.post("/index/tree", json={"url": "http://example.com"})
    assert response.status_code == 200
    assert "Indexed" in response.json()


async def test_list_indexed_pages_empty(ns_client):
    response = await ns_client.get("/index/pages")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_indexed_pages_after_indexing(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    response = await ns_client.get("/index/pages")
    assert response.status_code == 200
    assert any(p["url"] == "http://example.com/docs" for p in response.json())


async def test_clear_index_no_namespace(client):
    response = await client.delete("/index")
    assert response.status_code == 400


async def test_clear_index_success(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    response = await ns_client.delete("/index")
    assert response.status_code == 200
    assert "Deleted" in response.json()


async def test_search_no_namespace(client):
    response = await client.get("/search", params={"query": "hello"})
    assert response.status_code == 400


async def test_search_success(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    response = await ns_client.get("/search", params={"query": "documentation", "n_results": 3})
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert "references" in body
    assert isinstance(body["results"], list)
    assert isinstance(body["references"], list)


async def test_ask_no_namespace(client):
    response = await client.get("/ask", params={"query": "hello"})
    assert response.status_code == 400


async def test_ask_success(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    with patch("server.ask_agent", new=AsyncMock(return_value="This page documents the API.")):
        response = await ns_client.get("/ask", params={"query": "what is this about"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "This page documents the API."
    assert isinstance(body["references"], list)


async def test_ask_agent_failure_returns_400(ns_client):
    with patch("server._fetch", new=AsyncMock(return_value=_html_response(SIMPLE_HTML))):
        await ns_client.post("/index/page", json={"url": "http://example.com/docs"})
    with patch("server.ask_agent", new=AsyncMock(side_effect=RuntimeError("CLI crashed"))):
        response = await ns_client.get("/ask", params={"query": "what is this about"})
    assert response.status_code == 400
    assert "Agent call failed" in response.json()["detail"]


async def test_lifespan_shuts_down_agent_on_teardown():
    with patch("agent.shutdown", new=AsyncMock()) as mock_shutdown:
        async with _lifespan(app):
            mock_shutdown.assert_not_awaited()
    mock_shutdown.assert_awaited_once()


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


async def test_discover_links(client):
    linked_html = (
        '<html><body>'
        '<a href="/page-a">A</a>'
        '<a href="http://other.com/ext">Ext</a>'
        '</body></html>'
    )
    leaf = _html_response("<html><body>leaf</body></html>")

    async def mock_fetch(url):
        if url == "http://example.com/":
            return _html_response(linked_html)
        return leaf

    with patch("server._fetch", new=AsyncMock(side_effect=mock_fetch)):
        response = await client.get("/links", params={"url": "http://example.com/", "max_depth": 1})

    assert response.status_code == 200
    links = response.json()
    assert "http://example.com/" in links
    assert "http://example.com/page-a" in links
    assert "http://other.com/ext" not in links


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


async def test_delete_document_not_found(doc_client):
    client, _ = doc_client
    response = await client.delete("/documents/nonexistent.txt")
    assert response.status_code == 404


async def test_swagger_ui_returns_html(client):
    response = await client.get("/swagger-ui", params={"url": "/documents/api.json"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "swagger-ui" in response.text.lower()
    assert "/documents/api.json" in response.text


async def test_swagger_ui_missing_url_param(client):
    response = await client.get("/swagger-ui")
    assert response.status_code == 422


async def test_proxy_spec_returns_content(client):
    mock_resp = MagicMock()
    mock_resp.content = b'{"openapi": "3.0.0"}'
    mock_resp.headers = {"content-type": "application/json"}
    with patch("server._fetch", new=AsyncMock(return_value=mock_resp)):
        response = await client.get("/proxy/spec", params={"url": "https://api.example.com/openapi.json"})
    assert response.status_code == 200
    assert response.content == b'{"openapi": "3.0.0"}'


async def test_proxy_spec_fetch_failure_returns_502(client):
    with patch("server._fetch", new=AsyncMock(return_value=None)):
        response = await client.get("/proxy/spec", params={"url": "https://api.example.com/openapi.json"})
    assert response.status_code == 502


async def test_proxy_spec_rejects_non_http_url(client):
    response = await client.get("/proxy/spec", params={"url": "file:///etc/passwd"})
    assert response.status_code == 400
