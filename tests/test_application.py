import base64
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import mcp_tools
from router import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        yield http_client


async def test_namespace_changes_are_shared_between_mcp_and_http(client):
    mcp_tools.create_namespace("mcp-namespace")
    response = await client.get("/namespaces/current")
    assert response.json() == "mcp-namespace"

    await client.post("/namespaces", json={"name": "http-namespace"})
    assert mcp_tools.current_namespace() == "http-namespace"
    assert sorted(mcp_tools.list_namespaces()) == ["http-namespace", "mcp-namespace"]

    mcp_tools.use_namespace("mcp-namespace")
    response = await client.get("/namespaces/current")
    assert response.json() == "mcp-namespace"

    response = await client.delete("/namespaces/mcp-namespace")
    assert response.status_code == 200
    assert mcp_tools.current_namespace() == "No namespace selected."


async def test_mcp_upload_can_be_searched_and_deleted_over_http(client, tmp_uploads):
    mcp_tools.create_namespace("shared-documents")
    content = "Authentication requires a Bearer token in the Authorization header."
    result = mcp_tools.upload_document("guide.txt", base64.b64encode(content.encode()).decode())
    assert result == "Indexed 1 chunks from guide.txt"

    response = await client.get("/search", params={"query": "Bearer token", "n_results": 1})
    assert response.status_code == 200
    assert response.json()["references"] == ["file://shared-documents/guide.txt"]
    assert [item["text"] for item in response.json()["results"]] == [content]

    response = await client.delete("/documents/guide.txt")
    assert response.status_code == 200
    assert mcp_tools.list_documents() == []
    assert mcp_tools.list_indexed_pages() == []
    assert not (tmp_uploads / "shared-documents" / "guide.txt").exists()


async def test_http_upload_can_be_searched_and_cleared_over_mcp(client, tmp_uploads):
    await client.post("/namespaces", json={"name": "http-documents"})
    content = "Authentication requires a Bearer token in the Authorization header."
    response = await client.post("/documents", files={"file": ("guide.txt", content)})
    assert response.status_code == 200
    result = mcp_tools.search_docs("Bearer token", 1)
    assert result["references"] == ["file://http-documents/guide.txt"]
    assert [item["text"] for item in result["results"]] == [content]

    assert mcp_tools.clear_index() == "Deleted 1 documents from index."
    response = await client.get("/index/pages")
    assert response.json() == []


@pytest.mark.parametrize(
    ("tool_name", "arguments", "expected"),
    [
        ("current_namespace", (), "No namespace selected."),
        ("list_indexed_pages", (), []),
        ("list_documents", (), []),
        ("clear_index", (), "No namespace selected. Call use_namespace(name) first."),
        ("upload_document", ("guide.txt", ""), "No namespace selected. Call use_namespace(name) first."),
        ("delete_document", ("guide.txt",), "No namespace selected. Call use_namespace(name) first."),
        ("search_docs", ("question",), {"error": "No namespace selected. Call use_namespace(name) first."}),
    ],
)
def test_mcp_tools_preserve_no_namespace_responses(tool_name, arguments, expected):
    assert getattr(mcp_tools, tool_name)(*arguments) == expected


@pytest.mark.parametrize(
    ("tool_name", "expected"),
    [
        ("index_page", "No namespace selected. Call use_namespace(name) first."),
        ("ask", {"error": "No namespace selected. Call use_namespace(name) first."}),
    ],
)
async def test_async_mcp_tools_preserve_no_namespace_responses(tool_name, expected):
    assert await getattr(mcp_tools, tool_name)("https://example.com/docs") == expected


async def test_mcp_index_tree_reports_progress_and_http_sees_indexed_pages(client):
    mcp_tools.create_namespace("shared-pages")
    response = httpx.Response(200, text="<html><body><h1>Guide</h1><p>Documentation.</p></body></html>")
    context = MagicMock()
    context.info = AsyncMock()
    with patch("crawling.fetch", new=AsyncMock(return_value=response)):
        assert await mcp_tools.index_tree("https://example.com/docs", context, max_depth=0) == (
            "Indexed 1 pages (0 skipped, 0 failed) starting from https://example.com/docs"
        )
    context.info.assert_awaited_once_with("[indexed] https://example.com/docs")
    response = await client.get("/index/pages")
    assert response.json() == [{"url": "https://example.com/docs", "chunks": 1, "is_openapi": False}]


async def test_mcp_tool_registration_preserves_public_contract():
    tools = {tool.name: tool for tool in await mcp_tools.mcp.list_tools()}
    assert set(tools) == {
        "create_namespace", "use_namespace", "delete_namespace", "list_namespaces",
        "current_namespace", "index_page", "index_tree", "discover_links",
        "list_indexed_pages", "clear_index", "upload_document", "list_documents",
        "delete_document", "search_docs", "ask",
    }
    assert all(tool.description for tool in tools.values())
    assert set(tools["index_tree"].inputSchema["properties"]) == {"url", "max_depth", "force"}
    assert tools["index_tree"].inputSchema["properties"]["max_depth"]["default"] == 2
    assert tools["index_tree"].inputSchema["properties"]["force"]["default"] is False


def test_http_layer_import_does_not_load_mcp_entry_point():
    result = subprocess.run(
        [sys.executable, "-c", "import sys; import router; assert {'server', 'mcp_tools'}.isdisjoint(sys.modules)"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("http_first", [False, True])
async def test_both_lifespans_initialize_the_same_client_once(monkeypatch, tmp_path, http_first):
    import namespaces
    from router import _lifespan

    monkeypatch.setattr(namespaces, "chroma_client", None)
    monkeypatch.setattr(namespaces, "CHROMA_PATH", tmp_path / "chroma")
    persistent_client = MagicMock()
    lifespans = [_lifespan(app), mcp_tools.lifespan(mcp_tools.mcp)] if http_first else [
        mcp_tools.lifespan(mcp_tools.mcp), _lifespan(app)
    ]
    with patch("namespaces.chromadb.PersistentClient", return_value=persistent_client) as create_client, \
         patch("agent.shutdown", new=AsyncMock()):
        async with lifespans[0]:
            assert namespaces.chroma_client is persistent_client
            async with lifespans[1]:
                assert namespaces.chroma_client is persistent_client
        create_client.assert_called_once_with(path=str(tmp_path / "chroma"))
