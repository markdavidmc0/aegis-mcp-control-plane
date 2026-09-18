"""Control Plane to Data Plane Network Wire Contract Tests."""

import httpx
import pytest
from fastapi.testclient import TestClient

from src.control_plane.dependencies import get_data_plane_client
from src.control_plane.main import app as control_plane_app

cp_client = TestClient(control_plane_app)


@pytest.mark.contract
@pytest.mark.unauthenticated
def test_control_to_data_plane_wire_contract():
    """Verify identity headers and JSON-RPC payloads are correctly formatted on the wire."""
    captured_request: httpx.Request | None = None

    def mock_data_plane_handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 100, "result": {"status": "success", "tools": []}},
        )

    async def _get_mock_client():
        async with httpx.AsyncClient(
            base_url="http://dataplane.internal",
            transport=httpx.MockTransport(mock_data_plane_handler),
        ) as client:
            yield client

    control_plane_app.dependency_overrides[get_data_plane_client] = _get_mock_client

    headers = {
        "X-User-ID": "usr_contract_test",
        "X-User-Role": "admin",
        "X-User-Scopes": "tools:execute",
    }
    payload = {"jsonrpc": "2.0", "id": 100, "method": "tools/list"}

    response = cp_client.post("/mcp", json=payload, headers=headers)

    control_plane_app.dependency_overrides.pop(get_data_plane_client, None)

    assert response.status_code == 200
    assert captured_request is not None
    assert captured_request.headers["X-User-ID"] == "usr_contract_test"
    assert captured_request.headers["X-User-Role"] == "admin"
    assert captured_request.headers["X-User-Scopes"] == "tools:execute"
