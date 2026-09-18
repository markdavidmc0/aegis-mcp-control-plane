"""Integration tests for Unified Control Plane MCP Gateway Router at /mcp."""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from src.control_plane.main import app

DEFAULT_HEADERS = {
    "X-User-ID": "usr_mcp_integration_test",
    "X-User-Role": "developer",
    "X-User-Scopes": "tools:execute",
    "MCP-Protocol-Version": "2026-07-28",
}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_tools_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Issues JSON-RPC tools/list to /mcp and asserts built-in and dynamic catalog tools."""
    tools_dir = tmp_path / "arm_tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ARM_TOOLS_DIR", str(tools_dir))

    catalog_path = tools_dir / "catalog.json"
    catalog_data = {
        "tools": [
            {
                "name": "dynamic_test_tool",
                "description": "Dynamic catalog test tool",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
    }
    catalog_path.write_text(json.dumps(catalog_data), encoding="utf-8")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://controlplane.test",
        headers=DEFAULT_HEADERS,
    ) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "list-1",
            "method": "tools/list",
            "params": {},
        }

        response = await client.post("/mcp", json=payload)
        assert response.status_code == 200
        data = response.json()
        tool_names = [t["name"] for t in data["result"]["tools"]]
        assert "execute_code" in tool_names
        assert "dynamic_test_tool" in tool_names


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_tools_call_direct_execution() -> None:
    """Issues JSON-RPC tools/call for execute_code directly to /mcp."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://controlplane.test",
        headers=DEFAULT_HEADERS,
    ) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "call-direct-1",
            "method": "tools/call",
            "params": {
                "name": "execute_code",
                "arguments": {"code": "result = 21 * 2"},
            },
        }

        response = await client.post("/mcp", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data.get("jsonrpc") == "2.0"
        assert data.get("id") == "call-direct-1"
        assert "result" in data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_invalid_method() -> None:
    """Verifies unknown JSON-RPC methods return standard error code -32601."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://controlplane.test",
        headers=DEFAULT_HEADERS,
    ) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "invalid-1",
            "method": "nonexistent/method",
            "params": {},
        }

        response = await client.post("/mcp", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data.get("jsonrpc") == "2.0"
        assert data.get("id") == "invalid-1"
        assert "error" in data
        assert data["error"]["code"] == -32601
        assert "not found" in data["error"]["message"].lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_composite_identity_propagation() -> None:
    """Verifies that composite identity headers and URN are forwarded through router."""
    headers = {
        "X-User-ID": "usr_forward_test",
        "X-Actor-ID": "actor_forward_test",
        "X-Agent-ID": "agent_alpha",
        "X-Cost-Centre-ID": "cost_centre_beta",
        "X-Session-ID": "sess_gamma",
        "X-User-Role": "admin",
        "X-User-Scopes": "tools:execute",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://controlplane.test",
        headers=headers,
    ) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "propagate-1",
            "method": "tools/call",
            "params": {
                "name": "execute_code",
                "arguments": {"code": "result = 42"},
            },
        }

        response = await client.post("/mcp", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == "propagate-1"
        assert "result" in data
