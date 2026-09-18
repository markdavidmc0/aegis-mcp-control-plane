"""Integration tests for orchestrator handoff endpoint POST /api/v1/orchestrator/handoff."""

import pytest
from fastapi.testclient import TestClient

from src.orchestrator.registry import AgentRegistry
from src.orchestrator.router import get_orchestrator, get_registry
from src.orchestrator.runtime import AgentRuntimeOrchestrator
from src.orchestrator.schemas import AgentSpec, AgentTopology


@pytest.fixture
def clean_orchestrator_env(app) -> tuple[AgentRegistry, AgentRuntimeOrchestrator]:
    """Provides isolated registry and runtime orchestrator for testing handoffs."""
    reg = AgentRegistry()
    orch = AgentRuntimeOrchestrator(registry=reg)

    reg.register(
        AgentSpec(
            agent_id="supervisor-lead",
            name="Silicon Benchmark Lead",
            description="Supervisor agent",
            topology=AgentTopology.SUPERVISOR,
            system_prompt="Supervisor prompt",
            sub_agents=["worker-profiler", "worker-auditor"],
        )
    )
    reg.register(
        AgentSpec(
            agent_id="worker-profiler",
            name="Monty Kernel Profiler",
            description="Worker profiler",
            topology=AgentTopology.WORKER,
            system_prompt="Profiler prompt",
        )
    )
    reg.register(
        AgentSpec(
            agent_id="worker-auditor",
            name="Roofline Auditor",
            description="Worker auditor",
            topology=AgentTopology.WORKER,
            system_prompt="Auditor prompt",
        )
    )
    reg.register(
        AgentSpec(
            agent_id="standalone-agent",
            name="Standalone Agent",
            description="Standalone agent",
            topology=AgentTopology.STANDALONE,
            system_prompt="Standalone prompt",
        )
    )

    app.dependency_overrides[get_registry] = lambda: reg
    app.dependency_overrides[get_orchestrator] = lambda: orch
    yield reg, orch
    app.dependency_overrides.pop(get_registry, None)
    app.dependency_overrides.pop(get_orchestrator, None)


@pytest.mark.integration
def test_handoff_success_preserves_4tuple_keys(
    test_client: TestClient,
    clean_orchestrator_env: tuple[AgentRegistry, AgentRuntimeOrchestrator],
):
    """Test successful supervisor-to-worker handoff preserving 4-tuple keys.

    Asserts that:
    - HTTP 200 OK is returned.
    - Status is COMPLETED.
    - 4-tuple keys (X-Actor-ID, X-Cost-Centre-ID) are preserved from the caller.
    - Agent ID is updated to the target worker agent.
    - Session ID is prefixed with parent session ID.
    """
    custom_headers = {
        "X-Actor-ID": "actor_test_user_77",
        "X-User-ID": "actor_test_user_77",
        "X-Agent-ID": "supervisor-lead",
        "X-Cost-Centre-ID": "cost-centre-research-div",
        "X-Session-ID": "session_parent_root_1001",
    }

    payload = {
        "parent_session_id": "session_parent_root_1001",
        "caller_agent_id": "supervisor-lead",
        "target_agent_id": "worker-profiler",
        "task_instructions": "Profile kernel matrix multiplication",
        "context_data": {"matrix_dim": 2048, "precision": "fp32"},
    }

    res = test_client.post(
        "/api/v1/orchestrator/handoff",
        json=payload,
        headers=custom_headers,
    )

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["composite_key"]["actor_id"] == "actor_test_user_77"
    assert data["composite_key"]["cost_centre_id"] == "cost-centre-research-div"
    assert data["composite_key"]["agent_id"] == "worker-profiler"
    assert data["composite_key"]["session_id"].startswith("session_parent_root_1001-worker-profiler-")
    assert len(data["history"]) >= 1


@pytest.mark.integration
def test_handoff_rejected_if_caller_not_supervisor(
    test_client: TestClient,
    clean_orchestrator_env: tuple[AgentRegistry, AgentRuntimeOrchestrator],
):
    """Test handoff is rejected when caller is not configured as SUPERVISOR topology."""
    custom_headers = {
        "X-Actor-ID": "actor_test_user_77",
        "X-User-ID": "actor_test_user_77",
        "X-Agent-ID": "standalone-agent",
        "X-Cost-Centre-ID": "cost-centre-research-div",
        "X-Session-ID": "session_parent_root_1002",
    }

    payload = {
        "parent_session_id": "session_parent_root_1002",
        "caller_agent_id": "standalone-agent",
        "target_agent_id": "worker-profiler",
        "task_instructions": "Delegate unauthorized task",
        "context_data": {},
    }

    res = test_client.post(
        "/api/v1/orchestrator/handoff",
        json=payload,
        headers=custom_headers,
    )

    assert res.status_code == 400
    assert "not configured as a SUPERVISOR" in res.json()["detail"]


@pytest.mark.integration
def test_handoff_rejected_if_target_not_in_sub_agents(
    test_client: TestClient,
    clean_orchestrator_env: tuple[AgentRegistry, AgentRuntimeOrchestrator],
):
    """Test handoff is rejected when target agent is not in supervisor's sub_agents list."""
    custom_headers = {
        "X-Actor-ID": "actor_test_user_77",
        "X-User-ID": "actor_test_user_77",
        "X-Agent-ID": "supervisor-lead",
        "X-Cost-Centre-ID": "cost-centre-research-div",
        "X-Session-ID": "session_parent_root_1003",
    }

    payload = {
        "parent_session_id": "session_parent_root_1003",
        "caller_agent_id": "supervisor-lead",
        "target_agent_id": "standalone-agent",  # Not in sub_agents
        "task_instructions": "Attempting unauthorized subagent delegation",
        "context_data": {},
    }

    res = test_client.post(
        "/api/v1/orchestrator/handoff",
        json=payload,
        headers=custom_headers,
    )

    assert res.status_code == 400
    assert "not an authorized sub-agent" in res.json()["detail"]


@pytest.mark.integration
def test_handoff_rejected_if_caller_agent_not_found(
    test_client: TestClient,
    clean_orchestrator_env: tuple[AgentRegistry, AgentRuntimeOrchestrator],
):
    """Test handoff returns 404 when caller agent does not exist."""
    custom_headers = {
        "X-Actor-ID": "actor_test_user_77",
        "X-User-ID": "actor_test_user_77",
        "X-Agent-ID": "nonexistent-supervisor",
        "X-Cost-Centre-ID": "cost-centre-research-div",
        "X-Session-ID": "session_parent_root_1004",
    }

    payload = {
        "parent_session_id": "session_parent_root_1004",
        "caller_agent_id": "nonexistent-supervisor",
        "target_agent_id": "worker-profiler",
        "task_instructions": "Handoff from nonexistent agent",
        "context_data": {},
    }

    res = test_client.post(
        "/api/v1/orchestrator/handoff",
        json=payload,
        headers=custom_headers,
    )

    # When implemented, this endpoint should return 404 if caller agent is not found
    assert res.status_code == 404
    assert res.json().get("detail") == "Supervisor agent 'nonexistent-supervisor' is not registered."
