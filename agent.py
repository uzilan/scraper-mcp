import os

import claude_agent
import codex_agent


async def ask_agent(prompt: str, namespace: str) -> str:
    provider = os.environ.get("AGENT_PROVIDER", "claude")
    if provider == "claude":
        return await claude_agent.ask_agent(prompt, namespace)
    if provider == "codex":
        return await codex_agent.ask_agent(prompt, namespace)
    raise ValueError("AGENT_PROVIDER must be 'claude' or 'codex'.")


async def shutdown() -> None:
    await claude_agent.shutdown()
