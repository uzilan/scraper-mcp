import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_agent_sdk import AssistantMessage, TextBlock

import agent
import claude_agent
import mcp_tools


@pytest.fixture(autouse=True)
def reset_agent_client():
    claude_agent._client = None
    claude_agent._client_namespace = None
    yield
    claude_agent._client = None
    claude_agent._client_namespace = None


def _make_fake_client(reply_text):
    fake_client = MagicMock()
    fake_client.connect = AsyncMock()
    fake_client.disconnect = AsyncMock()
    fake_client.query = AsyncMock()

    async def fake_receive_response():
        yield AssistantMessage(content=[TextBlock(text=reply_text)], model="test-model")

    fake_client.receive_response = fake_receive_response
    return fake_client


async def test_ask_agent_connects_once_and_returns_text():
    fake_client = _make_fake_client("hello world")

    with patch("claude_agent.ClaudeSDKClient", return_value=fake_client) as ctor:
        result = await agent.ask_agent("what is up", "ns-a")
        assert result == "hello world"
        fake_client.connect.assert_awaited_once()
        fake_client.query.assert_awaited_once_with("what is up")

        # second call, same namespace: reuses the same connection, does not reconnect
        await agent.ask_agent("another question", "ns-a")
        ctor.assert_called_once()
        fake_client.connect.assert_awaited_once()
        fake_client.disconnect.assert_not_awaited()


async def test_ask_agent_disables_tools_and_setting_sources():
    fake_client = _make_fake_client("hello world")

    with patch("claude_agent.ClaudeSDKClient", return_value=fake_client) as ctor:
        await agent.ask_agent("what is up", "ns-a")

    options = ctor.call_args.kwargs["options"]
    assert options.tools == []
    assert options.setting_sources == []


async def test_ask_agent_drops_client_on_query_failure():
    broken_client = _make_fake_client("unused")
    broken_client.query = AsyncMock(side_effect=RuntimeError("CLI crashed"))
    recovered_client = _make_fake_client("recovered answer")

    with patch("claude_agent.ClaudeSDKClient", side_effect=[broken_client, recovered_client]) as ctor:
        with pytest.raises(RuntimeError):
            await agent.ask_agent("what is up", "ns-a")

        # next call in the same namespace must not reuse the broken client
        result = await agent.ask_agent("try again", "ns-a")
        assert result == "recovered answer"
        assert ctor.call_count == 2
        broken_client.disconnect.assert_awaited_once()


async def test_ask_agent_does_not_cache_client_on_connect_failure():
    # First call to ns-a succeeds, establishing _client_namespace == "ns-a".
    first_client = _make_fake_client("unused")
    first_client.query = AsyncMock(side_effect=RuntimeError("CLI crashed"))
    # A later call, still in ns-a (so the namespace-mismatch branch does NOT
    # fire), hits a connect() failure while rebuilding after the crash above.
    broken_client = MagicMock()
    broken_client.connect = AsyncMock(side_effect=RuntimeError("CLI not found"))
    broken_client.disconnect = AsyncMock()
    recovered_client = _make_fake_client("recovered answer")

    with patch("claude_agent.ClaudeSDKClient", side_effect=[first_client, broken_client, recovered_client]) as ctor:
        with pytest.raises(RuntimeError, match="CLI crashed"):
            await agent.ask_agent("what is up", "ns-a")

        with pytest.raises(RuntimeError, match="CLI not found"):
            await agent.ask_agent("try again", "ns-a")

        result = await agent.ask_agent("third try", "ns-a")
        assert result == "recovered answer"
        assert ctor.call_count == 3


async def test_ask_agent_serializes_concurrent_calls():
    order: list[str] = []
    fake_client = MagicMock()
    fake_client.connect = AsyncMock()
    fake_client.disconnect = AsyncMock()

    async def fake_query(prompt):
        order.append(f"query:{prompt}")

    def make_receive_response(prompt):
        async def fake_receive_response():
            await asyncio.sleep(0.01)
            order.append(f"yielded:{prompt}")
            yield AssistantMessage(content=[TextBlock(text=prompt)], model="test-model")
        return fake_receive_response()

    fake_client.query = AsyncMock(side_effect=fake_query)
    fake_client.receive_response = MagicMock(side_effect=lambda: make_receive_response(order[-1].split(":")[1]))

    with patch("claude_agent.ClaudeSDKClient", return_value=fake_client):
        await asyncio.gather(
            agent.ask_agent("first", "ns-a"),
            agent.ask_agent("second", "ns-a"),
        )

    assert order == ["query:first", "yielded:first", "query:second", "yielded:second"]


async def test_shutdown_disconnects_active_client():
    fake_client = _make_fake_client("hello world")

    with patch("claude_agent.ClaudeSDKClient", return_value=fake_client):
        await agent.ask_agent("what is up", "ns-a")

    await agent.shutdown()

    fake_client.disconnect.assert_awaited_once()
    assert claude_agent._client is None
    assert claude_agent._client_namespace is None


async def test_shutdown_is_a_noop_when_never_connected():
    # Must not raise even though no client was ever created.
    await agent.shutdown()
    assert claude_agent._client is None


async def test_mcp_lifespan_shuts_down_agent_on_teardown():
    with patch("agent.shutdown", new=AsyncMock()) as mock_shutdown, \
         patch("namespaces.chromadb.PersistentClient", return_value=MagicMock()):
        async with mcp_tools.lifespan(mcp_tools.mcp):
            mock_shutdown.assert_not_awaited()
    mock_shutdown.assert_awaited_once()


async def test_ask_agent_resets_session_on_namespace_change():
    first_client = _make_fake_client("answer for ns-a")
    second_client = _make_fake_client("answer for ns-b")

    with patch("claude_agent.ClaudeSDKClient", side_effect=[first_client, second_client]) as ctor:
        result_a = await agent.ask_agent("question 1", "ns-a")
        assert result_a == "answer for ns-a"

        result_b = await agent.ask_agent("question 2", "ns-b")
        assert result_b == "answer for ns-b"

        assert ctor.call_count == 2
        first_client.disconnect.assert_awaited_once()
        second_client.connect.assert_awaited_once()
