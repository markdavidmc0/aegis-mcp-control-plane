"""Contract Tests between Control Plane /mcp Gateway and Data Plane FastMCP Server."""

import httpx
import pytest
from fastapi.testclient import TestClient

from src.control_plane.dependencies import get_data_plane_client
from src.control_plane.main import app as control_plane_app
from src.data_plane.mcp_server import app as data_plane_app

cp_client = TestClient(control_plane_app)


@pytest.fixture(autouse=True)
def override_data_plane_client():
    """Connects Control Plane to Data Plane in-memory via AsyncClient ASGITransport."""
    async def _get_data_plane_client():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=data_plane_app),
            base_url="http://data-plane:8001",
        ) as client:
            yield client

    control_plane_app.dependency_overrides[get_data_plane_client] = _get_data_plane_client
    yield
    control_plane_app.dependency_overrides.pop(get_data_plane_client, None)


@pytest.mark.contract
def test_control_plane_to_data_plane_mcp_contract():
    """Verify end-to-end JSON-RPC contract forwarding over network boundary."""
    headers = {
        "X-User-ID": "usr_contract_e2e",
        "X-User-Role": "admin",
        "X-User-Scopes": "tools:execute",
    }

    # 1. Test server/discover contract
    discover_payload = {"jsonrpc": "2.0", "id": "init-1", "method": "server/discover"}
    res1 = cp_client.post("/mcp", json=discover_payload, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["result"]["serverInfo"]["name"] == "data-plane-mcp"

    # 2. Test tools/list contract
    list_payload = {"jsonrpc": "2.0", "id": "list-1", "method": "tools/list"}
    res2 = cp_client.post("/mcp", json=list_payload, headers=headers)
    assert res2.status_code == 200
    assert "tools" in res2.json()["result"]

    # 3. Test tools/call contract
    call_payload = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {"name": "execute_code", "arguments": {"code": "result = 42"}},
    }
    res3 = cp_client.post("/mcp", json=call_payload, headers=headers)
    assert res3.status_code == 200
    assert res3.json()["result"]["tool_name"] == "execute_code"
