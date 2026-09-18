"""Integration tests for OPA/Rego Policy Compliance Engine in Control Plane."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from src.control_plane.policy_engine import (
    PolicyDecision,
    PolicyEngine,
    PolicyEvaluationRequest,
)

from src.control_plane.main import app

DEFAULT_HEADERS = {
    "X-User-ID": "usr_policy_test_01",
    "X-User-Role": "developer",
    "X-User-Scopes": "tools:execute",
    "MCP-Protocol-Version": "2026-07-28",
}


@pytest.fixture
def policy_engine() -> PolicyEngine:
    """Fixture providing PolicyEngine initialized with project policy directory."""
    policies_dir = Path("policies")
    return PolicyEngine(policies_dir=policies_dir)


@pytest.mark.integration
def test_tool_call_allowed_with_valid_scope_and_bounds(policy_engine: PolicyEngine) -> None:
    """Tool call allowed when actor has tools:execute scope and arguments within bounds."""
    request = PolicyEvaluationRequest(
        policy_package="aegis.tools",
        input={
            "scope": "tools:execute",
            "tool": "profile_tensor_kernel",
            "arguments": {"matrix_dim": 4096},
        },
    )

    decision: PolicyDecision = policy_engine.evaluate(request)
    assert decision.allowed is True
    assert decision.violations == []


@pytest.mark.integration
def test_tool_call_denied_when_matrix_dim_exceeds_bounds(policy_engine: PolicyEngine) -> None:
    """Tool call DENIED when matrix_dim > 8192."""
    request = PolicyEvaluationRequest(
        policy_package="aegis.tools",
        input={
            "scope": "tools:execute",
            "tool": "profile_tensor_kernel",
            "arguments": {"matrix_dim": 16384},
        },
    )

    decision: PolicyDecision = policy_engine.evaluate(request)
    assert decision.allowed is False
    assert any("arguments_violation" in v or "matrix_dim" in v for v in decision.violations)


@pytest.mark.integration
def test_tool_call_denied_when_unsafe_code_detected(policy_engine: PolicyEngine) -> None:
    """Tool call DENIED when arguments contain unsafe os or system operations."""
    request = PolicyEvaluationRequest(
        policy_package="aegis.tools",
        input={
            "scope": "tools:execute",
            "tool": "execute_code",
            "arguments": {"code": "import os; os.system('rm -rf /')"},
        },
    )

    decision: PolicyDecision = policy_engine.evaluate(request)
    assert decision.allowed is False
    assert any("arguments_violation" in v or "unsafe" in v for v in decision.violations)


@pytest.mark.integration
def test_handoff_denied_when_caller_not_supervisor(policy_engine: PolicyEngine) -> None:
    """Handoff DENIED when caller topology is not SUPERVISOR."""
    request = PolicyEvaluationRequest(
        policy_package="aegis.handoff",
        input={
            "caller_topology": "WORKER",
            "target_agent_id": "worker-profiler",
            "authorized_targets": ["worker-profiler"],
        },
    )

    decision: PolicyDecision = policy_engine.evaluate(request)
    assert decision.allowed is False


@pytest.mark.integration
def test_handoff_denied_when_target_not_authorized(policy_engine: PolicyEngine) -> None:
    """Handoff DENIED when target agent is not in authorized_targets."""
    request = PolicyEvaluationRequest(
        policy_package="aegis.handoff",
        input={
            "caller_topology": "SUPERVISOR",
            "target_agent_id": "unauthorized-worker",
            "authorized_targets": ["worker-profiler", "worker-auditor"],
        },
    )

    decision: PolicyDecision = policy_engine.evaluate(request)
    assert decision.allowed is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_api_returns_policy_denial_error() -> None:
    """Integration with /api/v1/mcp returning policy denial error when policy violated."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://controlplane.test",
        headers=DEFAULT_HEADERS,
    ) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "policy-deny-1",
            "method": "tools/call",
            "params": {
                "name": "profile_tensor_kernel",
                "arguments": {"matrix_dim": 16384},
            },
        }

        response = await client.post("/api/v1/mcp", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("jsonrpc") == "2.0"
        assert data.get("id") == "policy-deny-1"
        assert "error" in data
        assert data["error"]["code"] == -32000 or "policy" in data["error"]["message"].lower()
