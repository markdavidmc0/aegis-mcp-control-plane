"""Integration tests for Control Plane LLM Proxy (/v1/chat/completions)."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.control_plane.main import app

client = TestClient(app)

DEFAULT_HEADERS = {
    "X-User-ID": "usr_dev_integration_001",
    "X-User-Role": "developer",
    "X-User-Scopes": "llm:proxy",
}


@pytest.mark.integration
def test_llm_proxy_missing_messages_validation():
    """Verifies POST /v1/chat/completions rejects requests without 'messages' with 400 Bad Request."""
    payload = {"model": "openai/gpt-4o"}
    response = client.post("/v1/chat/completions", json=payload, headers=DEFAULT_HEADERS)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "messages" in response.json()["detail"].lower()


@pytest.mark.integration
@pytest.mark.unauthenticated
def test_llm_proxy_missing_user_id_header():
    """Verifies request without X-User-ID header returns 401 Unauthorized."""
    payload = {
        "model": "openai/gpt-4o",
        "messages": [{"role": "user", "content": "Unauthenticated prompt"}],
    }
    response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Missing required upstream identity header" in response.json()["detail"]


@pytest.mark.integration
def test_llm_proxy_end_to_end_forwarding():
    """Verifies valid LLM proxy request forwards through dependency overrides cleanly."""
    payload = {
        "model": "openai/gpt-4o",
        "messages": [{"role": "user", "content": "Hello LLM"}],
    }
    response = client.post("/v1/chat/completions", json=payload, headers=DEFAULT_HEADERS)

    # 404 or 200 depending on whether Data Plane implements /v1/chat/completions
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND)


@pytest.mark.integration
def test_llm_proxy_composite_identity_propagation():
    """Verifies composite identity headers are accepted and processed by proxy."""
    headers = {
        "X-User-ID": "usr_proxy_test",
        "X-Actor-ID": "actor_proxy_test",
        "X-Agent-ID": "agent_llm",
        "X-Cost-Centre-ID": "cc_llm",
        "X-Session-ID": "sess_llm",
        "X-User-Role": "developer",
        "X-User-Scopes": "llm:proxy",
    }
    payload = {
        "model": "openai/gpt-4o",
        "messages": [{"role": "user", "content": "Hello LLM with composite identity"}],
    }
    response = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND)
