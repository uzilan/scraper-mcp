from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import application
import indexing
import namespaces
import search

SIMPLE_HTML = """
<html><body>
<h1>Authentication Guide</h1>
<p>Use bearer tokens to authenticate API calls. Include the token in the Authorization header.</p>
</body></html>
"""


@pytest.fixture
def ns():
    namespaces.create_namespace("test-ns")
    namespaces.use_namespace("test-ns")
    return namespaces.current_collection


def make_html_response(body: str) -> MagicMock:
    resp = MagicMock()
    resp.text = body
    resp.headers = {"content-type": "text/html"}
    resp.json.side_effect = Exception("not json")
    return resp


def test_list_indexed_pages_empty(ns):
    result = indexing.list_indexed_pages(ns)
    assert result == []


async def test_list_indexed_pages(ns):
    url = "http://example.com/docs"
    with patch("crawling.fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await indexing.index_page(ns, url)
    result = indexing.list_indexed_pages(ns)
    assert len(result) == 1
    assert result[0]["url"] == url
    assert result[0]["chunks"] > 0


async def test_clear_index(ns):
    url = "http://example.com/docs"
    with patch("crawling.fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await indexing.index_page(ns, url)
    assert ns.count() > 0
    result = indexing.clear_index(ns)
    assert "Deleted" in result
    assert ns.count() == 0


def test_clear_index_empty(ns):
    result = indexing.clear_index(ns)
    assert "already empty" in result.lower()


def test_search_docs_uses_original_query():
    collection = MagicMock()
    collection.name = "litellm"
    collection.count.return_value = 1
    collection.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    result = search.search_docs(collection, "how does it work?", n_results=1)
    collection.query.assert_called_once_with(query_texts=["how does it work?"], n_results=1)
    assert result == {"results": [], "references": []}


def test_search_docs_no_namespace():
    result = application.search_docs("auth tokens")
    assert "No namespace selected" in result["error"]


async def test_search_docs_returns_results(ns):
    url = "http://example.com/docs"
    with patch("crawling.fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await indexing.index_page(ns, url)
    result = search.search_docs(ns, "authentication bearer token")
    results = result["results"]
    assert len(results) > 0
    assert "source_url" in results[0]
    assert "text" in results[0]
    assert "relevance_score" in results[0]
    assert isinstance(result["references"], list)
