import asyncio
import json
import os
import signal
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory


def _mcp_overrides() -> list[str]:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    config_path = codex_home / "config.toml"
    if not config_path.exists():
        return []
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    servers = config.get("mcp_servers", {})
    if not servers:
        return []
    disabled_servers = ", ".join(
        f"{json.dumps(name)} = {{ enabled = false }}" for name in servers
    )
    return ["--config", f"mcp_servers={{{disabled_servers}}}"]


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except asyncio.TimeoutError:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        await process.wait()


async def ask_agent(prompt: str, namespace: str) -> str:
    with TemporaryDirectory(prefix="scraper-codex-") as workspace:
        output_path = Path(workspace) / "answer.txt"
        try:
            process = await asyncio.create_subprocess_exec(
                "codex", "--ask-for-approval", "never", "exec",
                "--ignore-rules", "--ephemeral",
                "--skip-git-repo-check", "--sandbox", "read-only",
                "--disable", "shell_tool", "--disable", "unified_exec",
                "--disable", "plugins", "--disable", "apps", "--disable", "hooks",
                *_mcp_overrides(),
                "--color", "never", "--output-last-message", str(output_path), "-",
                cwd=workspace,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name == "posix",
            )
        except FileNotFoundError as error:
            raise RuntimeError("Codex CLI not found. Install it on PATH and run 'codex login'.") from error
        try:
            await process.communicate(input=prompt.encode("utf-8"))
        finally:
            if process.returncode is None:
                await _stop_process(process)
        if process.returncode != 0:
            raise RuntimeError(
                f"Codex CLI exited with code {process.returncode}. "
                "Check 'codex login status' and your Codex CLI version."
            )
        answer = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
        if not answer:
            raise RuntimeError("Codex CLI returned no answer.")
        return answer
