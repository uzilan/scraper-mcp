import asyncio
import os
import signal
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def isolated_codex_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))


def make_process(returncode: int | None = 0):
    process = MagicMock()
    process.pid = 12345
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(b"progress output", b""))
    process.wait = AsyncMock(return_value=returncode)
    return process


async def test_codex_uses_local_auth_and_isolated_read_only_workspace(monkeypatch, tmp_path):
    import codex_agent

    codex_home = tmp_path / "existing-codex-home"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config = '''
model = "local-model"
model_provider = "company"
[model_providers.company]
base_url = "https://provider.example.com/v1"
env_key = "COMPANY_API_KEY"
[mcp_servers.scraper]
command = "uv"
[mcp_servers."server.with.dots"]
command = "tool"
'''
    config_path.write_text(config, encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    process = make_process()
    invocation = {}

    async def start_process(*arguments, **options):
        invocation.update(arguments=arguments, options=options)
        output_path = Path(arguments[arguments.index("--output-last-message") + 1])
        output_path.write_text("Codex answer\n", encoding="utf-8")
        return process

    prompt = "Question with 'quotes' and\nretrieved context; not a shell command"
    with patch("codex_agent.asyncio.create_subprocess_exec", new=AsyncMock(side_effect=start_process)):
        assert await codex_agent.ask_agent(prompt, "docs") == "Codex answer"

    arguments = invocation["arguments"]
    options = invocation["options"]
    assert arguments[:4] == ("codex", "--ask-for-approval", "never", "exec")
    assert arguments[-1] == "-"
    assert prompt not in arguments
    assert "--ignore-user-config" not in arguments
    overrides = [arguments[index + 1] for index, value in enumerate(arguments) if value == "--config"]
    assert overrides == [
        'mcp_servers={"scraper" = { enabled = false }, "server.with.dots" = { enabled = false }}',
    ]
    assert "--ignore-rules" in arguments
    assert "--ephemeral" in arguments
    assert "--skip-git-repo-check" in arguments
    assert arguments[arguments.index("--sandbox") + 1] == "read-only"
    disabled_features = [arguments[index + 1] for index, value in enumerate(arguments) if value == "--disable"]
    assert disabled_features == ["shell_tool", "unified_exec", "plugins", "apps", "hooks"]
    assert options["stdin"] == asyncio.subprocess.PIPE
    assert options["stdout"] == asyncio.subprocess.DEVNULL
    assert options["stderr"] == asyncio.subprocess.PIPE
    assert options["start_new_session"] is True
    assert "env" not in options
    process.communicate.assert_awaited_once_with(input=prompt.encode("utf-8"))
    assert not Path(options["cwd"]).exists()
    assert config_path.read_text(encoding="utf-8") == config


async def test_no_user_config_still_runs_with_cli_defaults(tmp_path, monkeypatch):
    import codex_agent

    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "missing-home"))
    process = make_process()
    process.communicate.return_value = (None, b"")

    async def start_process(*arguments, **options):
        output_path = Path(arguments[arguments.index("--output-last-message") + 1])
        output_path.write_text("answer", encoding="utf-8")
        return process

    with patch("codex_agent.asyncio.create_subprocess_exec", new=AsyncMock(side_effect=start_process)) as start:
        assert await codex_agent.ask_agent("question", "docs") == "answer"
    assert "--config" not in start.call_args.args


async def test_default_codex_home_is_checked_for_mcp_servers(tmp_path, monkeypatch):
    import codex_agent

    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('[mcp_servers.scraper]\ncommand = "uv"\n', encoding="utf-8")
    with patch("codex_agent.asyncio.create_subprocess_exec", new=AsyncMock(side_effect=FileNotFoundError)) as start:
        with pytest.raises(RuntimeError, match="Codex CLI not found"):
            await codex_agent.ask_agent("question", "docs")
    assert 'mcp_servers={"scraper" = { enabled = false }}' in start.call_args.args


async def test_missing_codex_cli_gives_actionable_error():
    import codex_agent

    with patch("codex_agent.asyncio.create_subprocess_exec", new=AsyncMock(side_effect=FileNotFoundError)):
        with pytest.raises(RuntimeError, match="Codex CLI.*PATH.*codex login"):
            await codex_agent.ask_agent("question", "docs")


async def test_failed_codex_command_does_not_return_partial_answer():
    import codex_agent

    process = make_process(returncode=1)
    process.communicate.return_value = (None, b"sensitive stderr details")
    with patch("codex_agent.asyncio.create_subprocess_exec", new=AsyncMock(return_value=process)):
        with pytest.raises(RuntimeError, match="Codex CLI exited.*1.*codex login status") as error:
            await codex_agent.ask_agent("question", "docs")
    assert "sensitive" not in str(error.value)


@pytest.mark.parametrize("answer", [None, "", "  \n"])
async def test_missing_or_empty_answer_fails(answer):
    import codex_agent

    async def start_process(*arguments, **options):
        if answer is not None:
            output_path = Path(arguments[arguments.index("--output-last-message") + 1])
            output_path.write_text(answer, encoding="utf-8")
        return make_process()

    with patch("codex_agent.asyncio.create_subprocess_exec", new=AsyncMock(side_effect=start_process)):
        with pytest.raises(RuntimeError, match="Codex CLI returned no answer"):
            await codex_agent.ask_agent("question", "docs")


async def test_cancellation_terminates_subprocess_and_removes_workspace():
    import codex_agent

    process = make_process(returncode=None)
    process.communicate.side_effect = asyncio.CancelledError
    with patch("codex_agent.asyncio.create_subprocess_exec", new=AsyncMock(return_value=process)) as start, \
         patch("codex_agent.os.killpg") as kill_group:
        with pytest.raises(asyncio.CancelledError):
            await codex_agent.ask_agent("question", "docs")
    if os.name == "posix":
        kill_group.assert_called_once_with(process.pid, signal.SIGTERM)
    else:
        process.terminate.assert_called_once_with()
    process.wait.assert_awaited_once_with()
    assert not Path(start.call_args.kwargs["cwd"]).exists()


async def test_unresponsive_subprocess_is_killed_after_termination_timeout():
    import codex_agent

    process = make_process(returncode=None)
    process.communicate.side_effect = asyncio.CancelledError
    process.wait.side_effect = [asyncio.TimeoutError, 0]
    with patch("codex_agent.asyncio.create_subprocess_exec", new=AsyncMock(return_value=process)), \
         patch("codex_agent.os.killpg") as kill_group:
        with pytest.raises(asyncio.CancelledError):
            await codex_agent.ask_agent("question", "docs")
    if os.name == "posix":
        assert [call.args for call in kill_group.call_args_list] == [
            (process.pid, signal.SIGTERM), (process.pid, signal.SIGKILL)
        ]
    else:
        process.kill.assert_called_once_with()
    assert process.wait.await_count == 2


def install_fake_codex(tmp_path, monkeypatch, source):
    executable = tmp_path / "codex"
    executable.write_text(f"#!{sys.executable}\n{source}", encoding="utf-8")
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))


async def test_real_subprocess_reads_stdin_and_returns_only_final_answer(tmp_path, monkeypatch):
    import codex_agent

    install_fake_codex(tmp_path, monkeypatch, """
import sys
from pathlib import Path

prompt = sys.stdin.read()
output_path = Path(sys.argv[sys.argv.index('--output-last-message') + 1])
output_path.write_text('Answer: ' + prompt, encoding='utf-8')
sys.stdout.write('progress is not the final answer')
sys.stderr.write('diagnostics are not the final answer')
""")
    assert await codex_agent.ask_agent("Résumé: Bearer token\nSecond line", "docs") == (
        "Answer: Résumé: Bearer token\nSecond line"
    )


async def test_real_subprocess_is_reaped_on_timeout(tmp_path, monkeypatch):
    import codex_agent

    install_fake_codex(tmp_path, monkeypatch, """
import time

time.sleep(30)
""")
    start_process = asyncio.create_subprocess_exec
    processes = []

    async def capture_process(*arguments, **options):
        process = await start_process(*arguments, **options)
        processes.append(process)
        return process

    with patch("codex_agent.asyncio.create_subprocess_exec", side_effect=capture_process) as start:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(codex_agent.ask_agent("question", "docs"), timeout=0.1)
    assert len(processes) == 1
    assert processes[0].returncode is not None
    assert not Path(start.call_args.kwargs["cwd"]).exists()
