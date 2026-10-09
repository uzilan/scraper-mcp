from unittest.mock import MagicMock, patch

import pytest

import server


def test_entry_point_uses_registered_mcp_instance():
    import mcp_tools

    assert server.mcp is mcp_tools.mcp
    assert not hasattr(server, "create_namespace")
    assert not hasattr(server, "lifespan")


@pytest.mark.parametrize("mcp_only", [False, True])
def test_main_selects_startup_mode(monkeypatch, mcp_only):
    if mcp_only:
        monkeypatch.setenv("MCP_ONLY", "1")
    else:
        monkeypatch.delenv("MCP_ONLY", raising=False)
    mcp_runner = MagicMock()
    combined_runner = MagicMock()
    run = MagicMock()
    with patch("server.mcp", new=MagicMock(run_stdio_async=mcp_runner)), \
         patch("server._run_all", new=combined_runner), \
         patch("server.asyncio.run", new=run):
        server.main()

    selected_runner = mcp_runner if mcp_only else combined_runner
    unselected_runner = combined_runner if mcp_only else mcp_runner
    selected_runner.assert_called_once_with()
    unselected_runner.assert_not_called()
    run.assert_called_once_with(selected_runner.return_value)
