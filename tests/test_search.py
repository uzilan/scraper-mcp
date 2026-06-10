from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import server

SIMPLE_HTML = """
<html><body>
<h1>Authentication Guide</h1>
<p>Use bearer tokens to authenticate API calls. Include the token in the Authorization header.</p>
</body></html>
"""


@pytest.fixture
def ns():
    server._create_namespace(server._chroma_client, "test-ns")
    server._use_namespace(server._chroma_client, "test-ns")
    return server._current_collection


def make_html_response(body: str) -> MagicMock:
    resp = MagicMock()
    resp.text = body
    resp.headers = {"content-type": "text/html"}
    resp.json.side_effect = Exception("not json")
    return resp


def test_list_indexed_pages_empty(ns):
    result = server._list_indexed_pages(ns)
    assert result == []


async def test_list_indexed_pages(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await server._index_page(ns, url)
    result = server._list_indexed_pages(ns)
    assert len(result) == 1
    assert result[0]["url"] == url
    assert result[0]["chunks"] > 0


async def test_clear_index(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await server._index_page(ns, url)
    assert ns.count() > 0
    result = server._clear_index(ns)
    assert "Deleted" in result
    assert ns.count() == 0


def test_clear_index_empty(ns):
    result = server._clear_index(ns)
    assert "already empty" in result.lower()


def test_search_docs_no_namespace():
    result = server._search_docs_tool("auth tokens")
    assert "No namespace selected" in result[0]["error"]


async def test_search_docs_returns_results(ns):
    url = "http://example.com/docs"
    with patch("server._fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await server._index_page(ns, url)
    results = server._search_docs(ns, "authentication bearer token")
    assert len(results) > 0
    assert "source_url" in results[0]
    assert "text" in results[0]
    assert "relevance_score" in results[0]
