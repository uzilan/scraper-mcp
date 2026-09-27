from unittest.mock import AsyncMock, patch

import pytest
import server


@pytest.fixture
def ns():
    server._create_namespace(server._chroma_client, "test-ns")
    server._use_namespace(server._chroma_client, "test-ns")
    return server._current_collection


async def test_ask_tool_no_namespace():
    result = await server._ask_tool("what is this about")
    assert result == {"error": "No namespace selected. Call use_namespace(name) first."}


async def test_ask_tool_empty_namespace(ns):
    result = await server._ask_tool("what is this about")
    assert result == {"error": "Namespace is empty. Call index_page(url) first."}


async def test_ask_returns_answer_with_references(ns):
    ns.add(
        documents=["Bearer tokens authenticate API requests via the Authorization header."],
        metadatas=[{"source_url": "http://example.com/auth"}],
        ids=["doc-1"],
    )
    with patch("server.ask_agent", new=AsyncMock(return_value="Use a Bearer token in the Authorization header.")) as mock_ask:
        result = await server._ask(ns, "how do I authenticate?")
    assert result["answer"] == "Use a Bearer token in the Authorization header."
    assert result["references"] == ["http://example.com/auth"]
    prompt, namespace = mock_ask.call_args.args
    assert "how do I authenticate?" in prompt
    assert "Bearer tokens authenticate" in prompt
    assert namespace == ns.name


async def test_ask_no_relevant_results_skips_agent_call(ns):
    ns.add(documents=["completely unrelated filler content"], metadatas=[{"source_url": "http://example.com/x"}], ids=["doc-1"])
    with patch("server._search_docs", return_value={"results": [], "references": []}) as mock_search, \
         patch("server.ask_agent", new=AsyncMock()) as mock_ask:
        result = await server._ask(ns, "how do I authenticate?")
    mock_search.assert_called_once()
    mock_ask.assert_not_called()
    assert result == {"answer": "No relevant content found in this namespace.", "references": []}
