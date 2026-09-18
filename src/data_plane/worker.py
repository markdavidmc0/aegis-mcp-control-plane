"""Unified Data Plane Worker & Execution Node.

Manages sandboxed code execution, catalog loading, and dynamic tool dispatching
for the Data Plane microservice.
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import logfire

try:
    import pydantic_monty as monty
except ImportError:
    monty = None

from src.config import resolve_tools_dir
from src.data_plane.schemas import (
    EXECUTE_CODE_TOOL_SCHEMA,
    DataPlaneUserContext,
)

logger = logging.getLogger("mvcp.data_plane_worker")
DEFAULT_TIMEOUT = float(os.environ.get("SANDBOX_TIMEOUT_SECONDS", "30.0"))


class DataPlaneSandboxRunner:
    """Executes Python code blocks safely inside isolated sandbox environments."""

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT):
        self.timeout_seconds = timeout_seconds

    async def execute_payload(
        self,
        code_snippet: str,
        user_context: DataPlaneUserContext | None = None,
        inputs: dict[str, Any] | None = None,
        external_lookup: dict[str, Callable[..., Any]] | None = None,
        backend: str | None = None,
    ) -> dict[str, Any]:
        """Executes a sanitized Python code snippet inside a sandbox boundary."""
        if user_context and "tools:execute" not in user_context.scopes:
            return {
                "status": "error",
                "error": "Access denied: Missing required 'tools:execute' scope.",
            }

        sanitized_code = self._sanitize_code(code_snippet)

        with logfire.span("sandbox.execute_payload", timeout=self.timeout_seconds):
            if backend == "subprocess":
                return await self.execute_subprocess(sanitized_code)
            if backend == "monty" and monty is not None:
                return await self.execute_monty(
                    sanitized_code, inputs=inputs, external_lookup=external_lookup
                )

            # Auto mode: Monty when external tools/inputs are supplied or default to subprocess
            if external_lookup and monty is not None:
                return await self.execute_monty(
                    sanitized_code, inputs=inputs, external_lookup=external_lookup
                )
            return await self.execute_subprocess(sanitized_code)

    def _sanitize_code(self, code_snippet: str) -> str:
        """Strips markdown code fences and whitespace."""
        sanitized = code_snippet.strip()
        if sanitized.startswith("```"):
            lines = sanitized.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            sanitized = "\n".join(lines).strip()
        return sanitized

    async def execute_subprocess(self, sanitized_code: str) -> dict[str, Any]:
        """Executes Python code inside a separate OS subprocess boundary."""
        harness_script = (
            "import sys, io, contextlib, json\n"
            "stdout_buf = io.StringIO()\n"
            "stderr_buf = io.StringIO()\n"
            "exec_globals = {'__name__': '__main__'}\n"
            "try:\n"
            "    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):\n"
            "        exec(sys.argv[1], exec_globals)\n"
            "    out = stdout_buf.getvalue().strip()\n"
            "    res = exec_globals.get('result', exec_globals.get('output', out))\n"
            "    print(json.dumps({'status': 'success', 'result': res, 'stdout': out}))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'status': 'error', 'error': str(e), 'stderr': stderr_buf.getvalue().strip()}))\n"
        )

        safe_env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "PYTHONPATH": os.path.pathsep.join(sys.path),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "HOME": os.environ.get("HOME", "/tmp"),
        }

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                harness_script,
                sanitized_code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=safe_env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout_seconds
            )

            raw_out = stdout.decode("utf-8").strip()
            if proc.returncode != 0 or not raw_out:
                err_msg = stderr.decode("utf-8").strip() or "Process exited with non-zero code."
                return {"status": "error", "error": err_msg}

            return json.loads(raw_out)

        except TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception as kill_err:
                logger.error(f"[SandboxRunner] Failed killing timed-out process: {kill_err}")
            return {
                "status": "error",
                "error": "Execution timed out: Sandbox process exceeded time limit.",
            }
        except Exception as err:
            return {"status": "error", "error": f"Sandbox runner error: {str(err)}"}

    async def execute_monty(
        self,
        sanitized_code: str,
        inputs: dict[str, Any] | None = None,
        external_lookup: dict[str, Callable[..., Any]] | None = None,
    ) -> dict[str, Any]:
        """Executes Python code in Rust-based Monty sandbox with external tool routing."""
        if monty is None:
            return {
                "status": "error",
                "error": "Pydantic Monty runtime is not available in environment.",
            }

        stdout_lines: list[str] = []

        def print_cb(stream: str, text: str) -> None:
            if stream == "stdout":
                stdout_lines.append(text)

        limits = monty.ResourceLimits(max_duration_secs=self.timeout_seconds)

        try:
            async with monty.AsyncMonty() as monty_engine:
                async with monty_engine.checkout(limits=limits) as session:
                    res = await session.feed_run(
                        sanitized_code,
                        inputs=inputs,
                        external_lookup=external_lookup,
                        print_callback=print_cb,
                    )

                    # Extract explicitly assigned 'result' or 'output' variables if present
                    extracted = await session.feed_run(
                        "try:\n"
                        "    __r__ = result\n"
                        "except NameError:\n"
                        "    try:\n"
                        "        __r__ = output\n"
                        "    except NameError:\n"
                        "        __r__ = None\n"
                        "__r__"
                    )

                    stdout_str = "".join(stdout_lines).strip()
                    final_result = (
                        extracted
                        if extracted is not None
                        else (res if res is not None else stdout_str)
                    )

                    return {
                        "status": "success",
                        "result": final_result,
                        "stdout": stdout_str,
                    }

        except Exception as err:
            err_msg = str(err)
            if "time limit exceeded" in err_msg.lower():
                return {
                    "status": "error",
                    "error": "Execution timed out: Sandbox process exceeded time limit.",
                }
            return {
                "status": "error",
                "error": f"Monty execution error: {err_msg}",
            }


class LocalToolDispatcher:
    """Dispatches tool execution calls locally to sub-process binaries or the sandbox runner."""

    def __init__(
        self,
        tools_dir: str | Path | None = None,
        timeout_seconds: float | None = None,
        sandbox_runner: DataPlaneSandboxRunner | None = None,
    ):
        self.tools_dir = Path(resolve_tools_dir(tools_dir))
        self.timeout_seconds = timeout_seconds or DEFAULT_TIMEOUT
        self.sandbox_runner = sandbox_runner or DataPlaneSandboxRunner(
            timeout_seconds=self.timeout_seconds
        )
        self._cached_catalog: list[dict[str, Any]] | None = None
        self._last_mtime: float = 0.0

    async def read_catalog(self) -> list[dict[str, Any]]:
        """Reads catalog.json with hot-reloading support, merging built-in execute_code schema."""
        catalog_path = self.tools_dir / "catalog.json"
        if catalog_path.exists():
            try:
                mtime = catalog_path.stat().st_mtime
                if mtime > self._last_mtime or self._cached_catalog is None:
                    with open(catalog_path, encoding="utf-8") as f:
                        data = json.load(f)
                        self._cached_catalog = (
                            data.get("tools", []) if isinstance(data, dict) else data
                        )
                        self._last_mtime = mtime
            except Exception as err:
                logger.error(f"[LocalToolDispatcher] Failed reading catalog.json: {err}")

        dynamic_tools = self._cached_catalog or []
        merged = {EXECUTE_CODE_TOOL_SCHEMA["name"]: EXECUTE_CODE_TOOL_SCHEMA}

        for dt in dynamic_tools:
            if isinstance(dt, dict) and "name" in dt:
                merged[dt["name"]] = dt

        return list(merged.values())

    def build_external_lookup(
        self,
        catalog: list[dict[str, Any]],
        loop: asyncio.AbstractEventLoop,
    ) -> dict[str, Callable[..., Any]]:
        """Builds an external lookup dictionary exposing catalog tools to Monty."""
        def make_invoker(t_name: str) -> Callable[..., Any]:
            def _invoke(*args: Any, **kwargs: Any) -> Any:
                call_args = kwargs if kwargs else (args[0] if args and isinstance(args[0], dict) else {})
                fut = asyncio.run_coroutine_threadsafe(
                    self.dispatch_tool_call(t_name, call_args), loop
                )
                res = fut.result(timeout=self.timeout_seconds)
                if isinstance(res, dict) and "result" in res and "output" in res["result"]:
                    return res["result"]["output"]
                return res
            return _invoke

        lookup: dict[str, Callable[..., Any]] = {}
        for tool in catalog:
            name = tool.get("name")
            if name and name != "execute_code":
                lookup[name] = make_invoker(name)

        lookup["call_tool"] = lambda name, **args: make_invoker(name)(**args)
        return lookup

    async def dispatch_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        user_context: DataPlaneUserContext | None = None,
    ) -> dict[str, Any]:
        """Dispatches execution for a target tool call."""
        start_time = time.perf_counter()
        args = arguments or {}

        # 1. Code Mode Execution (Process / Monty Sandbox)
        if tool_name == "execute_code":
            code_snippet = args.get("code") or args.get("code_snippet") or ""
            inputs = args.get("inputs")

            catalog = await self.read_catalog()
            loop = asyncio.get_running_loop()
            external_lookup = self.build_external_lookup(catalog, loop)

            res = await self.sandbox_runner.execute_payload(
                code_snippet=code_snippet,
                user_context=user_context,
                inputs=inputs,
                external_lookup=external_lookup,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

            if res.get("status") == "error":
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": res.get("error", "Sandbox Execution Failed"),
                    },
                }

            out_val = res.get("result")
            return {
                "jsonrpc": "2.0",
                "result": {
                    "tool_name": "execute_code",
                    "status": "SUCCESS",
                    "execution_time_ms": duration_ms,
                    "output": out_val,
                    "stdout": res.get("stdout", ""),
                    "content": [{"type": "text", "text": str(out_val)}],
                },
            }

        # 2. Dynamic Catalog Entrypoint Execution
        catalog = await self.read_catalog()
        tool_entry = next((t for t in catalog if t.get("name") == tool_name), None)

        if tool_entry and tool_entry.get("entrypoint"):
            entrypoint = tool_entry["entrypoint"]
            target_path = (self.tools_dir / entrypoint).resolve()

            # Security Guard: Path Traversal Check
            if not str(target_path).startswith(str(self.tools_dir.resolve())):
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Illegal path traversal detected for entrypoint '{entrypoint}'.",
                    },
                }

            if target_path.exists():
                return await self._execute_subprocess(
                    tool_name, str(target_path), args, start_time
                )

        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": f"Tool '{tool_name}' not found in catalog or entrypoint non-executable.",
            },
        }

    async def _execute_subprocess(
        self,
        tool_name: str,
        exec_path: str,
        args: dict[str, Any],
        start_time: float,
    ) -> dict[str, Any]:
        """Runs a tool binary or Python script as an async sub-process."""
        cmd = [sys.executable, exec_path] if exec_path.endswith(".py") else [exec_path]
        cmd.extend(["--json-args", json.dumps(args)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout_seconds
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

            raw_out = stdout.decode("utf-8").strip()
            try:
                parsed = json.loads(raw_out)
            except Exception:
                parsed = {"raw_output": raw_out}

            return {
                "jsonrpc": "2.0",
                "result": {
                    "tool_name": tool_name,
                    "status": "SUCCESS" if proc.returncode == 0 else "ERROR",
                    "execution_time_ms": duration_ms,
                    "output": parsed,
                    "stderr": stderr.decode("utf-8").strip(),
                },
            }
        except TimeoutError:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Tool '{tool_name}' execution timed out in sandbox.",
                },
            }
        except Exception as err:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Subprocess execution failed for '{tool_name}': {err}",
                },
            }


__all__ = [
    "DataPlaneSandboxRunner",
    "LocalToolDispatcher",
    "DEFAULT_TIMEOUT",
]
