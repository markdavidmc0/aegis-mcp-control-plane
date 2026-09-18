"""Async Integration Tests for Data Plane Standalone FastMCP Server (/api/v1/mcp)."""

import httpx
import pytest

from src.data_plane.context import get_current_user_context
from src.data_plane.mcp_server import app

DEFAULT_HEADERS = {
    "X-User-ID": "usr_mcp_test",
    "X-User-Role": "developer",
    "X-User-Scopes": "tools:execute",
}


@pytest.fixture
async def async_mcp_client():
    """Provides httpx.AsyncClient targeting the in-memory FastMCP ASGI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://dataplane.test", headers=DEFAULT_HEADERS
    ) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.unit
async def test_mcp_discover_method(async_mcp_client):
    """Verify 'server/discover' method returns FastMCP server capability metadata."""
    payload = {"jsonrpc": "2.0", "id": "init-1", "method": "server/discover"}
    response = await async_mcp_client.post("/api/v1/mcp", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["jsonrpc"] == "2.0"
    assert data["result"]["serverInfo"]["name"] == "data-plane-mcp"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_mcp_tools_list_method(async_mcp_client):
    """Verify 'tools/list' method returns catalog containing unified 'execute_code'."""
    payload = {"jsonrpc": "2.0", "id": "list-1", "method": "tools/list"}
    response = await async_mcp_client.post("/api/v1/mcp", json=payload)
    assert response.status_code == 200
    data = response.json()
    tool_names = [t["name"] for t in data["result"]["tools"]]
    assert "execute_code" in tool_names


@pytest.mark.asyncio
@pytest.mark.unit
async def test_mcp_tools_call_execution(async_mcp_client):
    """Verify 'tools/call' method executes code snippet safely."""
    payload = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "execute_code",
            "arguments": {"code": "result = 1 + 1"},
        },
    }
    response = await async_mcp_client.post("/api/v1/mcp", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["tool_name"] == "execute_code"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_identity_header_extraction_and_context_reset(async_mcp_client):
    """Verify identity contextvar is set during request and reset immediately after."""
    assert get_current_user_context() is None

    payload = {"jsonrpc": "2.0", "id": "header-1", "method": "server/discover"}
    response = await async_mcp_client.post("/api/v1/mcp", json=payload)
    assert response.status_code == 200

    # ContextVar must reset back to None
    assert get_current_user_context() is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_mcp_batch_request_rejection(async_mcp_client):
    """Verify batch JSON-RPC requests (arrays) are explicitly rejected."""
    batch_payload = [
        {"jsonrpc": "2.0", "id": 1, "method": "server/discover"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    response = await async_mcp_client.post("/api/v1/mcp", json=batch_payload)
    assert response.status_code == 422

@pytest.mark.asyncio
@pytest.mark.unit
async def test_data_plane_direct_call_missing_identity():
    """Verify direct Data Plane call without X-User-ID header returns 401."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://dataplane.test",
    ) as unauth_client:
        payload = {"jsonrpc": "2.0", "id": "1", "method": "server/discover"}
        response = await unauth_client.post("/api/v1/mcp", json=payload)
        assert response.status_code == 401
        assert "Missing required header" in response.json()["detail"]

@pytest.mark.asyncio
@pytest.mark.unit
async def test_mcp_method_not_found_error(async_mcp_client):
    """Verify unknown MCP method returns JSON-RPC error code -32601."""
    payload = {
        "jsonrpc": "2.0",
        "id": "err-32601",
        "method": "invalid/method_name",
    }
    response = await async_mcp_client.post("/api/v1/mcp", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["error"]["code"] == -32601
    assert "not found" in data["error"]["message"].lower()
