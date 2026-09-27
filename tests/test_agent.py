from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_agent_sdk import AssistantMessage, TextBlock

import agent


@pytest.fixture(autouse=True)
def reset_agent_client():
    agent._client = None
    agent._client_namespace = None
    yield
    agent._client = None
    agent._client_namespace = None


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

    with patch("agent.ClaudeSDKClient", return_value=fake_client) as ctor:
        result = await agent.ask_agent("what is up", "ns-a")
        assert result == "hello world"
        fake_client.connect.assert_awaited_once()
        fake_client.query.assert_awaited_once_with("what is up")

        # second call, same namespace: reuses the same connection, does not reconnect
        await agent.ask_agent("another question", "ns-a")
        ctor.assert_called_once()
        fake_client.connect.assert_awaited_once()
        fake_client.disconnect.assert_not_awaited()


async def test_ask_agent_resets_session_on_namespace_change():
    first_client = _make_fake_client("answer for ns-a")
    second_client = _make_fake_client("answer for ns-b")

    with patch("agent.ClaudeSDKClient", side_effect=[first_client, second_client]) as ctor:
        result_a = await agent.ask_agent("question 1", "ns-a")
        assert result_a == "answer for ns-a"

        result_b = await agent.ask_agent("question 2", "ns-b")
        assert result_b == "answer for ns-b"

        assert ctor.call_count == 2
        first_client.disconnect.assert_awaited_once()
        second_client.connect.assert_awaited_once()
