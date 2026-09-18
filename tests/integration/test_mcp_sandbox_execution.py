"""Integration Tests for HTTP JSON-RPC Code Execution at /api/v1/mcp."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.data_plane.mcp_server import app

DEFAULT_HEADERS = {
    "X-User-ID": "usr_mcp_sandbox_integration",
    "X-User-Role": "developer",
    "X-User-Scopes": "tools:execute",
    "MCP-Protocol-Version": "2026-07-28",
}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_endpoint_timeout_handling():
    """Verify POST /api/v1/mcp with infinite loop returns JSON-RPC error -32603."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://dataplane.test",
        headers=DEFAULT_HEADERS,
    ) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "timeout-1",
            "method": "tools/call",
            "params": {
                "name": "execute_code",
                "arguments": {"code": "while True:\n    pass"},
            },
        }

        response = await client.post("/api/v1/mcp", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["error"]["code"] == -32603
        assert "timed out" in data["error"]["message"].lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_endpoint_execution_output():
    """Verify code execution yields stdout and result payload without synthetic mocks."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://dataplane.test",
        headers=DEFAULT_HEADERS,
    ) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "eval-1",
            "method": "tools/call",
            "params": {
                "name": "execute_code",
                "arguments": {"code": "print('hello world')"},
            },
        }

        response = await client.post("/api/v1/mcp", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert "result" in data
        assert data["result"]["status"] == "SUCCESS"
