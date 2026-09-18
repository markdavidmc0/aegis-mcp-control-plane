"""Deterministic Infrastructure & Service Plumbing Test Suite.

Validates process sandbox isolation limits, network reachability, and
gateway protocol proxying without requiring third-party LLM keys.
"""

import pytest

from src.data_plane.schemas import DataPlaneUserContext
from src.data_plane.worker import DataPlaneSandboxRunner


@pytest.mark.asyncio
async def test_gateway_health_and_service_reachability(api_client):
    """Assert control plane gateway readiness and health status."""
    res = await api_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_control_plane_mcp_routing(api_client):
    """Validate gateway MCP JSON-RPC protocol handling and tool list routing."""
    tools_list_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    mcp_res = await api_client.post("/mcp", json=tools_list_req)
    assert mcp_res.status_code == 200
    assert "tools" in mcp_res.json()["result"]


@pytest.mark.asyncio
async def test_sandbox_runner_process_isolation():
    """Verify DataPlaneSandboxRunner process isolation and timeout safety."""
    runner = DataPlaneSandboxRunner(timeout_seconds=1.0)
    user_ctx = DataPlaneUserContext(
        user_id="usr_infra_test", role="admin", scopes=["tools:execute"]
    )

    # Fast execution check
    res_success = await runner.execute_payload("result = 100 + 200", user_context=user_ctx)
    assert res_success["status"] == "success"
    assert res_success["result"] == 300

    # Timeout safety check
    res_timeout = await runner.execute_payload("while True: pass", user_context=user_ctx)
    assert res_timeout["status"] == "error"
    assert "timed out" in res_timeout["error"].lower()
