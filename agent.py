from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, TextBlock

_client: ClaudeSDKClient | None = None
_client_namespace: str | None = None


async def _get_client(namespace: str) -> ClaudeSDKClient:
    global _client, _client_namespace
    if _client is not None and _client_namespace != namespace:
        await _client.disconnect()
        _client = None
    if _client is None:
        _client = ClaudeSDKClient(options=ClaudeAgentOptions(allowed_tools=[], max_turns=1))
        await _client.connect()
        _client_namespace = namespace
    return _client


async def ask_agent(prompt: str, namespace: str) -> str:
    client = await _get_client(namespace)
    await client.query(prompt)
    parts: list[str] = []
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    return "".join(parts)
