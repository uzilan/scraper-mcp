import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import server

SIMPLE_HTML = """
<html><body>
<h1>Hello</h1>
<p>This is some documentation content that should be indexed.</p>
</body></html>
"""

OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "summary": "List items",
                "tags": ["items"],
                "parameters": [],
            }
        }
    },
}


def make_html_response(body: str) -> MagicMock:
    resp = MagicMock()
    resp.text = body
    resp.headers = {"content-type": "text/html"}
    resp.json.side_effect = Exception("not json")
    return resp


def make_json_response(body: dict) -> MagicMock:
    resp = MagicMock()
    resp.text = json.dumps(body)
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = body
    return resp


@pytest.fixture
def ns():
    server._create_namespace(server._chroma_client, "test-ns")
    server._use_namespace(server._chroma_client, "test-ns")
    return server._current_collection


async def test_index_page_html(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        result = await server._index_page(ns, url)
    assert "Indexed" in result
    assert url in result
    assert ns.count() > 0


async def test_index_page_openapi(ns):
    url = "http://example.com/openapi.json"
    with patch("server._fetch", new=AsyncMock(return_value=make_json_response(OPENAPI_SPEC))):
        result = await server._index_page(ns, url)
    assert "operations" in result
    assert ns.count() > 0


async def test_index_page_no_namespace():
    result = await server._index_page_tool("http://example.com/docs")
    assert "No namespace selected" in result


async def test_index_page_fetch_failure(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=None)):
        result = await server._index_page(ns, url)
    assert "Failed" in result
