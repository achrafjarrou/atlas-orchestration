# atlas/mcp/servers/code.py — Sandboxed Python execution
# Safety: whitelist builtins, block dangerous imports, 10s timeout

import asyncio, io, traceback, time
from contextlib import redirect_stdout, redirect_stderr
from typing import Any
import structlog
from atlas.mcp.registry import MCPTool, mcp_registry

logger = structlog.get_logger(__name__)

SAFE_BUILTINS = {
    "print": print, "len": len, "range": range, "enumerate": enumerate,
    "zip": zip, "map": map, "filter": filter, "list": list, "dict": dict,
    "set": set, "tuple": tuple, "str": str, "int": int, "float": float,
    "bool": bool, "sorted": sorted, "reversed": reversed, "min": min,
    "max": max, "sum": sum, "abs": abs, "round": round, "isinstance": isinstance,
    "type": type, "repr": repr, "format": format,
    "True": True, "False": False, "None": None,
    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
}

FORBIDDEN = ["import os", "import sys", "import subprocess", "__import__",
             "open(", "exec(", "eval(", "socket", "urllib", "requests", "httpx"]


async def run_python(code: str, timeout_seconds: int = 10) -> dict[str, Any]:
    """Execute Python in a safe sandbox. Set `result` variable to return a value."""
    start = time.time()
    for pat in FORBIDDEN:
        if pat in code:
            return {"output": "", "result": None, "error": f"Forbidden: '{pat}'", "execution_time_ms": 0}
    stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
    ns: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    error = None
    result_value = None

    def _exec():
        nonlocal error, result_value
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                exec(compile(code, "<atlas_sandbox>", "exec"), ns)
                result_value = ns.get("result")
            except Exception:
                error = traceback.format_exc()

    try:
        await asyncio.wait_for(asyncio.to_thread(_exec), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        error = f"Timed out after {timeout_seconds}s"

    return {"output": stdout_buf.getvalue(), "result": str(result_value) if result_value is not None else None,
            "error": error or stderr_buf.getvalue() or None, "execution_time_ms": int((time.time()-start)*1000)}


def register_code_tools():
    mcp_registry.register(MCPTool(id="run_python", name="Run Python",
        description="Execute Python code safely. No file system or network access. Set `result` variable to return a value.",
        category="code", handler=run_python, tags=["python", "code", "compute"]))
    logger.info("code_tools_ready")