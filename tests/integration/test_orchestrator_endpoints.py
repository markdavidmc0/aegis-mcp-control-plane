import pytest
from fastapi.testclient import TestClient

from src.orchestrator.registry import AgentRegistry
from src.orchestrator.router import get_orchestrator, get_registry
from src.orchestrator.runtime import AgentRuntimeOrchestrator
from src.orchestrator.schemas import AgentSpec, AgentTopology


@pytest.fixture
def clean_registry(app) -> AgentRegistry:
    """Fixture providing an isolated registry override for endpoints."""
    reg = AgentRegistry()
    orch = AgentRuntimeOrchestrator(registry=reg)
    app.dependency_overrides[get_registry] = lambda: reg
    app.dependency_overrides[get_orchestrator] = lambda: orch
    yield reg
    app.dependency_overrides.pop(get_registry, None)
    app.dependency_overrides.pop(get_orchestrator, None)


@pytest.mark.integration
def test_orchestrator_specs_crud_endpoints(test_client: TestClient, clean_registry: AgentRegistry):
    """Test POST, GET list, and GET by ID for agent specs."""
    payload = {
        "agent_id": "api-agent-1",
        "name": "API Agent One",
        "description": "Agent exposed via API",
        "topology": "STANDALONE",
        "model": "gpt-4o",
        "system_prompt": "You are an API-managed agent.",
        "allowed_tools": ["fetch_data"],
        "sub_agents": [],
        "max_steps": 10,
        "timeout_seconds": 60.0,
    }

    # Register spec
    res = test_client.post("/api/v1/orchestrator/specs", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["agent_id"] == "api-agent-1"

    # List specs
    res = test_client.get("/api/v1/orchestrator/specs")
    assert res.status_code == 200
    specs = res.json()
    assert len(specs) == 1
    assert specs[0]["agent_id"] == "api-agent-1"

    # Get single spec
    res = test_client.get("/api/v1/orchestrator/specs/api-agent-1")
    assert res.status_code == 200
    assert res.json()["name"] == "API Agent One"

    # Non-existent spec 404
    res = test_client.get("/api/v1/orchestrator/specs/does-not-exist")
    assert res.status_code == 404


@pytest.mark.integration
def test_orchestrator_runs_and_session_endpoints(test_client: TestClient, clean_registry: AgentRegistry):
    """Test running an agent and querying/cancelling sessions."""
    spec = AgentSpec(
        agent_id="run-agent-1",
        name="Run Agent One",
        description="Run test",
        topology=AgentTopology.STANDALONE,
        system_prompt="Execute test",
    )
    clean_registry.register(spec)

    # Initiate run
    run_payload = {
        "prompt": "Test run execution via API",
        "context": {"priority": "high"},
    }
    res = test_client.post("/api/v1/orchestrator/runs/run-agent-1", json=run_payload)
    assert res.status_code == 200
    session_data = res.json()
    assert session_data["status"] == "COMPLETED"
    session_id = session_data["session_id"]
    assert session_id is not None

    # Get session
    res = test_client.get(f"/api/v1/orchestrator/sessions/{session_id}")
    assert res.status_code == 200
    assert res.json()["session_id"] == session_id

    # Cancel session
    res = test_client.post(f"/api/v1/orchestrator/sessions/{session_id}/cancel")
    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"

    # 404 for unknown session
    res = test_client.get("/api/v1/orchestrator/sessions/non-existent-session-id")
    assert res.status_code == 404
