from unittest.mock import AsyncMock, patch

import pytest

import agent


async def test_default_provider_is_claude():
    with patch("claude_agent.ask_agent", new=AsyncMock(return_value="Claude answer")) as ask:
        assert await agent.ask_agent("question", "docs") == "Claude answer"
    ask.assert_awaited_once_with("question", "docs")


@pytest.mark.parametrize("provider", ["claude", "codex"])
async def test_configured_provider_receives_prompt_and_namespace(monkeypatch, provider):
    monkeypatch.setenv("AGENT_PROVIDER", provider)
    with patch("claude_agent.ask_agent", new=AsyncMock(return_value="answer")) as ask_claude, \
         patch("codex_agent.ask_agent", new=AsyncMock(return_value="answer")) as ask_codex:
        assert await agent.ask_agent("question and retrieved context", "docs") == "answer"
    selected_agent = ask_codex if provider == "codex" else ask_claude
    unselected_agent = ask_claude if provider == "codex" else ask_codex
    selected_agent.assert_awaited_once_with("question and retrieved context", "docs")
    unselected_agent.assert_not_awaited()


async def test_invalid_provider_fails_without_falling_back(monkeypatch):
    monkeypatch.setenv("AGENT_PROVIDER", "unknown")
    with patch("claude_agent.ask_agent", new=AsyncMock()) as ask_claude, \
         patch("codex_agent.ask_agent", new=AsyncMock()) as ask_codex:
        with pytest.raises(ValueError, match="AGENT_PROVIDER.*claude.*codex"):
            await agent.ask_agent("question", "docs")
    ask_claude.assert_not_awaited()
    ask_codex.assert_not_awaited()


async def test_shutdown_closes_claude_client_even_after_provider_change(monkeypatch):
    monkeypatch.setenv("AGENT_PROVIDER", "codex")
    with patch("claude_agent.shutdown", new=AsyncMock()) as shutdown:
        await agent.shutdown()
    shutdown.assert_awaited_once_with()
