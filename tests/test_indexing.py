import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import application
import crawling
import indexing
import namespaces

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


def make_plain_response(body: str) -> MagicMock:
    resp = MagicMock()
    resp.text = body
    resp.headers = {"content-type": "text/plain"}
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
    namespaces.create_namespace("test-ns")
    namespaces.use_namespace("test-ns")
    return namespaces.current_collection


async def test_index_page_html(ns):
    url = "http://example.com/docs"
    with patch("crawling.fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        result = await indexing.index_page(ns, url)
    assert "Indexed" in result
    assert url in result
    assert ns.count() > 0


async def test_index_page_openapi(ns):
    url = "http://example.com/openapi.json"
    with patch("crawling.fetch", new=AsyncMock(return_value=make_json_response(OPENAPI_SPEC))):
        result = await indexing.index_page(ns, url)
    assert "operations" in result
    assert ns.count() > 0


async def test_index_page_no_namespace():
    result = await application.index_page("http://example.com/docs")
    assert "No namespace selected" in result


async def test_index_page_fetch_failure(ns):
    url = "http://example.com/docs"
    with patch("crawling.fetch", new=AsyncMock(return_value=None)):
        result = await indexing.index_page(ns, url)
    assert "Failed" in result


async def test_index_tree_single_page(ns):
    url = "http://example.com/"
    with patch("crawling.fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        result = await indexing.index_tree(ns, url)
    assert "Indexed 1" in result


async def test_index_tree_skips_already_indexed(ns):
    url = "http://example.com/"
    with patch("crawling.fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await indexing.index_tree(ns, url)
        result = await indexing.index_tree(ns, url)
    assert "skipped" in result


async def test_index_tree_no_namespace():
    result = await application.index_tree("http://example.com/")
    assert "No namespace selected" in result


LINKED_HTML = """
<html><body>
<a href="/page-a">Page A</a>
<a href="/page-b">Page B</a>
<a href="http://other.com/external">External</a>
</body></html>
"""


async def test_discover_links_same_domain_only():
    url = "http://example.com/"
    leaf = make_html_response("<html><body>leaf</body></html>")

    async def mock_fetch(u):
        if u == url:
            return make_html_response(LINKED_HTML)
        return leaf

    with patch("crawling.fetch", new=AsyncMock(side_effect=mock_fetch)):
        result = await crawling.discover_links(url, max_depth=1)

    assert url in result
    assert "http://example.com/page-a" in result
    assert "http://example.com/page-b" in result
    assert "http://other.com/external" not in result


async def test_index_tree_log_indexed(ns):
    url = "http://example.com/"
    logged = []
    async def collect(msg): logged.append(msg)
    with patch("crawling.fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await indexing.index_tree(ns, url, log=collect)
    assert any("[indexed]" in m and url in m for m in logged)


async def test_index_tree_log_failed_fetch(ns):
    url = "http://example.com/"
    logged = []
    async def collect(msg): logged.append(msg)
    with patch("crawling.fetch", new=AsyncMock(return_value=None)):
        await indexing.index_tree(ns, url, log=collect)
    assert any("[failed]" in m and url in m for m in logged)


async def test_discover_links_log_callback():
    url = "http://example.com/"
    logged = []
    async def collect(u): logged.append(u)
    leaf = make_html_response("<html><body>leaf</body></html>")
    with patch("crawling.fetch", new=AsyncMock(return_value=leaf)):
        result = await crawling.discover_links(url, max_depth=0, log=collect)
    assert url in logged
    assert url in result


LLMS_TXT = """# Example Docs

- [Page A](http://example.com/page-a): Doc page A
- [Page B](http://example.com/page-b): Doc page B
"""

PAGE_WITH_NAV = """
<html><body>
<nav><a href="/nav-1">Nav 1</a><a href="/nav-2">Nav 2</a></nav>
<h1>Content</h1>
</body></html>
"""


async def test_index_tree_llms_txt_does_not_follow_html_links(ns):
    """Pages discovered via llms.txt markdown links are treated as leaves:
    their HTML nav links must not be followed even when depth allows it."""
    fetched = []

    async def mock_fetch(u):
        fetched.append(u)
        if u == "http://example.com/llms.txt":
            return make_plain_response(LLMS_TXT)
        return make_html_response(PAGE_WITH_NAV)

    with patch("crawling.fetch", new=AsyncMock(side_effect=mock_fetch)):
        result = await indexing.index_tree(ns, "http://example.com/llms.txt", max_depth=2)

    indexed_urls = {m["source_url"] for m in ns.get()["metadatas"]}
    assert "http://example.com/llms.txt" in indexed_urls
    assert "http://example.com/page-a" in indexed_urls
    assert "http://example.com/page-b" in indexed_urls
    # nav links from page-a / page-b must NOT be indexed
    assert "http://example.com/nav-1" not in indexed_urls
    assert "http://example.com/nav-2" not in indexed_urls


async def test_list_indexed_pages_flags_openapi(ns):
    url = "http://example.com/openapi.json"
    with patch("crawling.fetch", new=AsyncMock(return_value=make_json_response(OPENAPI_SPEC))):
        await indexing.index_page(ns, url)
    pages = indexing.list_indexed_pages(ns)
    assert len(pages) == 1
    assert pages[0]["url"] == url
    assert pages[0]["is_openapi"] is True


async def test_list_indexed_pages_html_not_openapi(ns):
    url = "http://example.com/docs"
    with patch("crawling.fetch", new=AsyncMock(return_value=make_html_response(SIMPLE_HTML))):
        await indexing.index_page(ns, url)
    pages = indexing.list_indexed_pages(ns)
    assert len(pages) == 1
    assert pages[0]["is_openapi"] is False


async def test_discover_links_llms_txt_does_not_follow_html_links():
    """discover_links starting from a plain-text file must not expand
    HTML nav links from the pages the file lists."""

    async def mock_fetch(u):
        if u == "http://example.com/llms.txt":
            return make_plain_response(LLMS_TXT)
        return make_html_response(PAGE_WITH_NAV)

    with patch("crawling.fetch", new=AsyncMock(side_effect=mock_fetch)):
        result = await crawling.discover_links("http://example.com/llms.txt", max_depth=2)

    assert "http://example.com/llms.txt" in result
    assert "http://example.com/page-a" in result
    assert "http://example.com/page-b" in result
    assert "http://example.com/nav-1" not in result
    assert "http://example.com/nav-2" not in result
