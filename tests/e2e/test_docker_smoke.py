"""Post-`docker compose up` Container Stack Verification Suite.

Executes live HTTP network assertions against containerized services (ports 8000/8001)
to verify inter-service reachability, gVisor sandbox execution, and header propagation.
"""

import pytest

DEFAULT_HEADERS = {
    "X-User-ID": "usr_docker_smoke",
    "X-User-Role": "admin",
    "X-User-Scopes": "tools:execute,read,llm:proxy",
    "MCP-Protocol-Version": "2026-07-28",
}


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_live_gateway_health(api_client):
    """1. Verify Control Plane container is responsive and healthy."""
    res = await api_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_live_mcp_direct_repl_execution(api_client):
    """2. Verify Control-to-Data-Plane HTTP proxying & containerized REPL execution."""
    payload = {
        "jsonrpc": "2.0",
        "id": "docker-smoke-01",
        "method": "tools/call",
        "params": {
            "name": "execute_code",
            "arguments": {
                "code": "import sys; print(f'Python {sys.version_info.major}.{sys.version_info.minor} in sandbox')"
            },
        },
    }

    res = await api_client.post("/api/v1/mcp", json=payload, headers=DEFAULT_HEADERS)
    assert res.status_code == 200

    data = res.json()
    assert data.get("jsonrpc") == "2.0"
    assert "result" in data
    assert data["result"]["status"] == "SUCCESS"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_live_llm_proxy_reachability(api_client):
    """3. Verify Control Plane /v1/chat/completions route validation."""
    invalid_payload = {"model": "openai/gpt-4o"}
    res = await api_client.post(
        "/v1/chat/completions",
        json=invalid_payload,
        headers=DEFAULT_HEADERS,
    )
    assert res.status_code == 400
    assert "messages" in res.json()["detail"].lower()
