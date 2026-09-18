"""Decoupled Control & Data Plane E2E Workflow Test Suite.

Validates complete decoupled orchestration flows across:
- Direct Gateway MCP JSON-RPC Routing (/mcp & /api/v1/mcp)
- OpenAI-Compatible LLM Proxy Gateway (/v1/chat/completions)
- Atomic Catalog Tool Registration (/api/v1/tools/register)
- Zero-Trust Identity Claim Enforcement & Header Propagation
"""

import pytest

DEFAULT_HEADERS = {
    "X-User-ID": "usr_e2e_decoupled_tester",
    "X-User-Role": "developer",
    "X-User-Scopes": "tools:execute,read,tools:register",
    "MCP-Protocol-Version": "2026-07-28",
}


# ==============================================================================
# 1. Zero-Trust Identity Header Enforcement
# ==============================================================================


@pytest.mark.e2e
@pytest.mark.unauthenticated
@pytest.mark.asyncio
async def test_decoupled_zero_trust_unauthenticated_rejection(api_client):
    """Verify that requests lacking X-User-ID are rejected at the Control Plane boundary with HTTP 401."""
    payload = {
        "name": "e2e_unauth_tool",
        "description": "Tool for testing unauthenticated submission.",
        "parameters": {"type": "object", "properties": {}},
    }

    res = await api_client.post(
        "/api/v1/tools/register",
        json=payload,
        headers={"X-User-ID": ""},
    )
    assert res.status_code == 401
    assert "Missing required upstream identity header" in res.json()["detail"]


# ==============================================================================
# 2. Direct Gateway MCP JSON-RPC Routing
# ==============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_decoupled_mcp_tools_list_discovery(api_client):
    """Verify JSON-RPC 2.0 tools/list request over /mcp endpoint catalogs available tools."""
    req_payload = {
        "jsonrpc": "2.0",
        "id": "e2e-mcp-list-1",
        "method": "tools/list",
        "params": {},
    }

    res = await api_client.post("/mcp", json=req_payload, headers=DEFAULT_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == "e2e-mcp-list-1"
    assert "tools" in data["result"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_decoupled_mcp_direct_code_execution(api_client):
    """Verify direct JSON-RPC tools/call for execute_code proxies payload to Data Plane REPL."""
    req_payload = {
        "jsonrpc": "2.0",
        "id": "e2e-mcp-call-1",
        "method": "tools/call",
        "params": {
            "name": "execute_code",
            "arguments": {
                "code": "result = [x * 2 for x in range(4)]; print(result)"
            },
        },
    }

    res = await api_client.post("/api/v1/mcp", json=req_payload, headers=DEFAULT_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == "e2e-mcp-call-1"
    assert "result" in data
    assert data["result"]["status"] == "SUCCESS"


# ==============================================================================
# 3. Dynamic Tool Registration Workflow
# ==============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_decoupled_tool_registration_and_list(api_client):
    """Verify register tool via POST /api/v1/tools/register and reflect in /mcp tools/list."""
    register_payload = {
        "name": "e2e_vector_dot",
        "description": "Calculates SME2 vector dot product.",
        "parameters": {
            "type": "object",
            "properties": {"len": {"type": "integer"}},
        },
    }

    reg_res = await api_client.post(
        "/api/v1/tools/register", json=register_payload, headers=DEFAULT_HEADERS
    )
    assert reg_res.status_code == 200
    assert reg_res.json()["status"] == "registered"

    list_payload = {"jsonrpc": "2.0", "id": "e2e-check-reg", "method": "tools/list"}
    list_res = await api_client.post("/mcp", json=list_payload, headers=DEFAULT_HEADERS)
    assert list_res.status_code == 200
    tool_names = [t["name"] for t in list_res.json()["result"]["tools"]]
    assert "e2e_vector_dot" in tool_names
