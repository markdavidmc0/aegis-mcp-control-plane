"""Contract Tests for Code Mode Execution Patterns on Data Plane."""

import pytest
from fastapi.testclient import TestClient

from src.data_plane.mcp_server import app as data_plane_app

client = TestClient(data_plane_app)

HEADERS = {
    "X-User-ID": "usr_contract_001",
    "X-User-Role": "developer",
    "X-User-Scopes": "tools:execute",
}


@pytest.mark.contract
def test_codemode_direct_execution_contract():
    """Verify execute_code runs code payloads via Data Plane process sandbox."""
    code = "result = 21 * 2\nprint(f'Calculated: {result}')"
    payload = {
        "jsonrpc": "2.0",
        "id": "req-exec-01",
        "method": "tools/call",
        "params": {
            "name": "execute_code",
            "arguments": {"code": code},
        },
    }
    response = client.post("/api/v1/mcp", json=payload, headers=HEADERS)
    assert response.status_code == 200

    data = response.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == "req-exec-01"
    assert data["result"]["status"] == "SUCCESS"
    assert data["result"]["output"] == 42
    assert data["result"]["stdout"] == "Calculated: 42"


@pytest.mark.contract
def test_codemode_timeout_protection_contract():
    """Verify sandbox runner halts infinite loops safely."""
    infinite_loop_code = "while True:\n    pass"
    payload = {
        "jsonrpc": "2.0",
        "id": "req-loop-01",
        "method": "tools/call",
        "params": {
            "name": "execute_code",
            "arguments": {"code": infinite_loop_code},
        },
    }
    response = client.post("/api/v1/mcp", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == -32603
    assert "timed out" in data["error"]["message"].lower()
