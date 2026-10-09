import asyncio
import os

import uvicorn

from mcp_tools import mcp


async def _run_all() -> None:
    from router import app as http_app

    port = int(os.environ.get("HTTP_PORT", "8000"))
    config = uvicorn.Config(http_app, host="0.0.0.0", port=port, log_level="error", access_log=False)
    http_server = uvicorn.Server(config)

    mcp_task = asyncio.create_task(mcp.run_stdio_async())
    http_task = asyncio.create_task(http_server.serve())

    try:
        # Exit as soon as either service stops (Ctrl+C stops uvicorn first)
        await asyncio.wait([mcp_task, http_task], return_when=asyncio.FIRST_COMPLETED)

        # Cancel whichever is still running; give it 2 s to clean up
        for task in (mcp_task, http_task):
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
                except Exception:
                    pass
    finally:
        # Always force-exit: covers both clean shutdown and a second Ctrl+C that
        # cancels this coroutine before os._exit would otherwise be reached.
        # The MCP stdio task may be stuck on a blocking stdin read that asyncio
        # cancellation cannot interrupt, so we must not rely on normal cleanup.
        os._exit(0)


def main() -> None:
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        if os.environ.get("MCP_ONLY"):
            asyncio.run(mcp.run_stdio_async())
        else:
            asyncio.run(_run_all())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass



if __name__ == "__main__":
    main()
