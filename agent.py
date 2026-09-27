import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, TextBlock

_client: ClaudeSDKClient | None = None
_client_namespace: str | None = None
_lock = asyncio.Lock()


async def _get_client(namespace: str) -> ClaudeSDKClient:
    global _client, _client_namespace
    if _client is not None and _client_namespace != namespace:
        await _client.disconnect()
        _client = None
    if _client is None:
        candidate = ClaudeSDKClient(
            options=ClaudeAgentOptions(tools=[], setting_sources=[], max_turns=1)
        )
        await candidate.connect()
        _client = candidate
        _client_namespace = namespace
    return _client


async def shutdown() -> None:
    global _client, _client_namespace
    async with _lock:
        if _client is not None:
            await _client.disconnect()
            _client = None
            _client_namespace = None


async def ask_agent(prompt: str, namespace: str) -> str:
    global _client
    async with _lock:
        client = await _get_client(namespace)
        try:
            await client.query(prompt)
            parts: list[str] = []
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
            return "".join(parts)
        except Exception:
            await client.disconnect()
            _client = None
            raise
