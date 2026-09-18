"""Contract tests for Envoy Edge Guard pre-authenticated UserContext dependency interface."""

import pytest
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient

from src.control_plane.dependencies import UserContext, get_user_context

app = FastAPI()


@app.get("/test-user-context")
async def sample_route(user: UserContext = Depends(get_user_context)):
    """Sample endpoint for validating get_user_context header extraction."""
    composite_urn = user.composite_key.urn if user.composite_key else None
    return {
        "user_id": user.user_id,
        "role": user.role,
        "scopes": user.scopes,
        "urn": composite_urn,
        "actor_id": user.composite_key.actor_id if user.composite_key else None,
        "agent_id": user.composite_key.agent_id if user.composite_key else None,
        "cost_centre_id": user.composite_key.cost_centre_id if user.composite_key else None,
        "session_id": user.composite_key.session_id if user.composite_key else None,
    }


client = TestClient(app)


@pytest.mark.contract
def test_user_context_valid_headers():
    """Verify get_user_context parses downstream Envoy identity headers correctly."""
    headers = {
        "X-User-ID": "usr_99",
        "X-User-Role": "admin",
        "X-User-Scopes": "read, write",
    }
    response = client.get("/test-user-context", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["user_id"] == "usr_99"
    assert data["role"] == "admin"
    assert data["scopes"] == ["read", "write"]
    assert data["actor_id"] == "usr_99"
    assert data["agent_id"] == "default-agent"
    assert data["cost_centre_id"] == "default-cost-centre"
    assert data["session_id"] == "default-session"
    assert data["urn"] == "urn:aegis:agent:usr_99:default-agent:default-cost-centre:default-session"


@pytest.mark.contract
def test_user_context_default_fallbacks():
    """Verify get_user_context sets default role and empty scopes when headers are missing."""
    headers = {"X-User-ID": "usr_42"}
    response = client.get("/test-user-context", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["user_id"] == "usr_42"
    assert data["role"] == "user"
    assert data["scopes"] == []
    assert data["urn"] == "urn:aegis:agent:usr_42:default-agent:default-cost-centre:default-session"


@pytest.mark.contract
def test_user_context_empty_or_whitespace_scopes():
    """Verify get_user_context correctly handles empty strings and trailing commas in scopes."""
    headers = {
        "X-User-ID": "usr_42",
        "X-User-Scopes": "read, , write , ",
    }
    response = client.get("/test-user-context", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["scopes"] == ["read", "write"]


@pytest.mark.contract
def test_user_context_missing_x_user_id():
    """Verify get_user_context enforces HTTP 401 when X-User-ID header is missing."""
    response = client.get("/test-user-context")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Missing required upstream identity header" in response.json()["detail"]


@pytest.mark.contract
def test_user_context_explicit_composite_headers():
    """Verify get_user_context extracts explicit 4-tuple identity headers."""
    headers = {
        "X-Actor-ID": "sec_operator_1",
        "X-Agent-ID": "autonomous_triage",
        "X-Cost-Centre-ID": "security_ops",
        "X-Session-ID": "session_9876",
        "X-User-Role": "sec_lead",
        "X-User-Scopes": "audit,remediate",
    }
    response = client.get("/test-user-context", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["user_id"] == "sec_operator_1"
    assert data["actor_id"] == "sec_operator_1"
    assert data["agent_id"] == "autonomous_triage"
    assert data["cost_centre_id"] == "security_ops"
    assert data["session_id"] == "session_9876"
    assert data["urn"] == "urn:aegis:agent:sec_operator_1:autonomous_triage:security_ops:session_9876"


@pytest.mark.contract
def test_user_context_invalid_composite_header_pattern():
    """Verify get_user_context rejects malformed characters in composite identity headers."""
    headers = {
        "X-User-ID": "valid_user",
        "X-Agent-ID": "bad agent with spaces",
    }
    response = client.get("/test-user-context", headers=headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid composite identity headers" in response.json()["detail"]
