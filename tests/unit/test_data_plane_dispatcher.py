"""Unit Tests for Data Plane Sandbox Runner and LocalToolDispatcher."""

import json
import os
import time
from pathlib import Path

import pytest

from src.data_plane.schemas import DataPlaneUserContext
from src.data_plane.worker import DataPlaneSandboxRunner, LocalToolDispatcher


@pytest.mark.asyncio
@pytest.mark.unit
async def test_sandbox_executes_in_separate_process():
    """Verify code execution occurs inside a separate process ID from host process."""
    runner = DataPlaneSandboxRunner(timeout_seconds=5.0)
    user_ctx = DataPlaneUserContext(user_id="usr_test", role="dev", scopes=["tools:execute"])
    code = "import os\nresult = os.getpid()"

    res = await runner.execute_payload(code, user_context=user_ctx)
    assert res["status"] == "success"
    assert res["result"] != os.getpid()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_path_traversal_prevention_dot_dot(tmp_path: Path):
    """Verify path traversal attempts return -32601 / -32602 error codes."""
    dispatcher = LocalToolDispatcher(tools_dir=tmp_path)
    traversal_targets = ["../../../bin/sh", "../../etc/passwd", "/etc/passwd"]

    for target in traversal_targets:
        res = await dispatcher.dispatch_tool_call(target, {"arg": "val"})
        assert res["jsonrpc"] == "2.0"
        assert "error" in res
        assert res["error"]["code"] in [-32601, -32602]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_subprocess_timeout_mapping(tmp_path: Path):
    """Verify subprocess timing out maps to -32603 Internal Error."""
    slow_binary = tmp_path / "slow_tool.py"
    slow_binary.write_text("import time\ntime.sleep(5.0)\n", encoding="utf-8")

    catalog = {"tools": [{"name": "slow_tool", "entrypoint": "slow_tool.py"}]}
    (tmp_path / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")

    dispatcher = LocalToolDispatcher(tools_dir=tmp_path, timeout_seconds=0.1)
    res = await dispatcher.dispatch_tool_call("slow_tool", {})

    assert res["jsonrpc"] == "2.0"
    assert "error" in res
    assert res["error"]["code"] == -32603
    assert "timed out" in res["error"]["message"].lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_catalog_hot_reloading_on_mtime_change(tmp_path: Path):
    """Verifies updating catalog.json st_mtime triggers automatic reloading."""
    tools_dir = tmp_path / "tools_dir"
    tools_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = tools_dir / "catalog.json"

    catalog_v1 = {"tools": [{"name": "tool_v1", "description": "Version 1"}]}
    catalog_path.write_text(json.dumps(catalog_v1), encoding="utf-8")

    dispatcher = LocalToolDispatcher(tools_dir=tools_dir)
    tools1 = await dispatcher.read_catalog()
    assert any(t.get("name") == "tool_v1" for t in tools1)

    time.sleep(0.05)
    catalog_v2 = {"tools": [{"name": "tool_v1"}, {"name": "tool_v2"}]}
    catalog_path.write_text(json.dumps(catalog_v2), encoding="utf-8")
    new_mtime = catalog_path.stat().st_mtime + 1.0
    os.utime(catalog_path, (new_mtime, new_mtime))

    tools2 = await dispatcher.read_catalog()
    assert any(t.get("name") == "tool_v2" for t in tools2)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_monty_execution_and_tool_wiring():
    """Verify Monty executes python snippet and successfully invokes wired catalog tool."""
    dispatcher = LocalToolDispatcher()
    code = (
        "specs = get_accelerator_specs()\n"
        "arch = specs['architecture']\n"
        "peak = specs['peak_tflops']\n"
        "result = {'arch': arch, 'peak_doubled': peak * 2}\n"
    )

    res = await dispatcher.dispatch_tool_call(
        tool_name="execute_code",
        arguments={"code": code},
        user_context=DataPlaneUserContext(
            user_id="usr_monty_test",
            role="developer",
            scopes=["tools:execute"],
        ),
    )

    assert res["jsonrpc"] == "2.0"
    assert "result" in res
    assert res["result"]["status"] == "SUCCESS"
    assert res["result"]["output"]["arch"] == "vortex-npu-v2"
    assert res["result"]["output"]["peak_doubled"] == 256.0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_monty_timeout_protection():
    """Verify Monty runner handles timeout and returns clean error structure."""
    runner = DataPlaneSandboxRunner(timeout_seconds=0.1)
    res = await runner.execute_monty("while True:\n    pass")
    assert res["status"] == "error"
    assert "timed out" in res["error"].lower()

