import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import application
import namespaces
import search


@pytest.fixture
def ns():
    namespaces.create_namespace("test-ns")
    namespaces.use_namespace("test-ns")
    return namespaces.current_collection


async def test_ask_tool_no_namespace():
    result = await application.ask("what is this about")
    assert result == {"error": "No namespace selected. Call use_namespace(name) first."}


async def test_ask_tool_empty_namespace(ns):
    result = await application.ask("what is this about")
    assert result == {"error": "Namespace is empty. Call index_page(url) first."}


async def test_ask_returns_answer_with_references(ns):
    ns.add(
        documents=["Bearer tokens authenticate API requests via the Authorization header."],
        metadatas=[{"source_url": "http://example.com/auth"}],
        ids=["doc-1"],
    )
    with patch("search.ask_agent", new=AsyncMock(return_value="Use a Bearer token in the Authorization header.")) as mock_ask:
        result = await search.ask(ns, "how do I authenticate?")
    assert result["answer"] == "Use a Bearer token in the Authorization header."
    assert result["references"] == ["http://example.com/auth"]
    prompt, namespace = mock_ask.call_args.args
    assert "how do I authenticate?" in prompt
    assert "Bearer tokens authenticate" in prompt
    assert namespace == ns.name


async def test_ask_includes_namespace_in_search_query():
    collection = MagicMock()
    collection.name = "litellm"
    collection.count.return_value = 1
    collection.query.return_value = {
        "documents": [["LiteLLM provides an SDK and a proxy for language models."]],
        "metadatas": [[{"source_url": "http://example.com/litellm"}]],
        "distances": [[0.5]],
    }
    with patch("search.ask_agent", new=AsyncMock(return_value="Use the SDK or proxy.")) as mock_ask:
        result = await search.ask(collection, "how does it work?", n_results=1)
    collection.query.assert_called_once_with(query_texts=["litellm: how does it work?"], n_results=1)
    assert result == {
        "answer": "Use the SDK or proxy.",
        "references": ["http://example.com/litellm"],
    }
    prompt, namespace = mock_ask.call_args.args
    assert prompt.endswith("Question: how does it work?")
    assert "LiteLLM provides an SDK and a proxy" in prompt
    assert namespace == "litellm"


async def test_ask_no_relevant_results_skips_agent_call(ns):
    ns.add(documents=["completely unrelated filler content"], metadatas=[{"source_url": "http://example.com/x"}], ids=["doc-1"])
    with patch("search.search_docs", return_value={"results": [], "references": []}) as mock_search, \
         patch("search.ask_agent", new=AsyncMock()) as mock_ask:
        result = await search.ask(ns, "how do I authenticate?")
    mock_search.assert_called_once()
    mock_ask.assert_not_called()
    assert result == {"answer": "No relevant content found in this namespace.", "references": []}


async def test_ask_returns_error_when_agent_call_fails(ns):
    ns.add(
        documents=["Bearer tokens authenticate API requests via the Authorization header."],
        metadatas=[{"source_url": "http://example.com/auth"}],
        ids=["doc-1"],
    )
    with patch("search.ask_agent", new=AsyncMock(side_effect=RuntimeError("CLI crashed"))):
        result = await search.ask(ns, "how do I authenticate?")
    assert result == {"error": "Agent call failed: CLI crashed"}


async def test_ask_tool_surfaces_agent_error(ns):
    ns.add(
        documents=["Bearer tokens authenticate API requests via the Authorization header."],
        metadatas=[{"source_url": "http://example.com/auth"}],
        ids=["doc-1"],
    )
    with patch("search.ask_agent", new=AsyncMock(side_effect=RuntimeError("CLI crashed"))):
        result = await application.ask("how do I authenticate?")
    assert result == {"error": "Agent call failed: CLI crashed"}


async def test_ask_times_out_slow_agent_call(ns):
    ns.add(
        documents=["Bearer tokens authenticate API requests via the Authorization header."],
        metadatas=[{"source_url": "http://example.com/auth"}],
        ids=["doc-1"],
    )

    async def slow_ask_agent(prompt, namespace):
        await asyncio.sleep(10)
        return "too slow"

    with patch("search.ask_agent", new=slow_ask_agent), patch("search.ASK_TIMEOUT_SECONDS", 0.05):
        result = await search.ask(ns, "how do I authenticate?")
    assert result == {"error": "Agent call timed out"}


async def test_ask_filters_out_zero_relevance_chunks_even_if_search_docs_returns_them(ns):
    # _search_docs's own relevance_score <= 0 filter is not part of this
    # feature's committed code, so _ask must not rely on it: it filters
    # zero/negative-relevance chunks itself before building the prompt.
    fake_retrieved = {
        "results": [
            {"text": "Bearer tokens go in the Authorization header.", "source_url": "http://example.com/auth", "relevance_score": 0.42},
            {"text": "Unrelated banana bread recipe.", "source_url": "http://example.com/recipe", "relevance_score": 0.0},
        ],
        "references": ["http://example.com/auth", "http://example.com/recipe"],
    }
    with patch("search.search_docs", return_value=fake_retrieved), \
         patch("search.ask_agent", new=AsyncMock(return_value="Use a Bearer token.")) as mock_ask:
        result = await search.ask(ns, "how do I authenticate?")
    prompt, _namespace = mock_ask.call_args.args
    assert "Bearer tokens go in the Authorization header" in prompt
    assert "banana bread" not in prompt
    assert result["references"] == ["http://example.com/auth"]


async def test_ask_all_chunks_irrelevant_skips_agent_call(ns):
    fake_retrieved = {
        "results": [
            {"text": "Unrelated banana bread recipe.", "source_url": "http://example.com/recipe", "relevance_score": 0.0},
        ],
        "references": ["http://example.com/recipe"],
    }
    with patch("search.search_docs", return_value=fake_retrieved), \
         patch("search.ask_agent", new=AsyncMock()) as mock_ask:
        result = await search.ask(ns, "how do I authenticate?")
    mock_ask.assert_not_called()
    assert result == {"answer": "No relevant content found in this namespace.", "references": []}
