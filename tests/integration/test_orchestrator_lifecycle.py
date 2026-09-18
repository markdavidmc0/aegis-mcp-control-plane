"""Integration Lifecycle Test: Deploy Mock Agent, Execute Work, Teardown.

Demonstrates end-to-end deployment of a mock agent in the runtime orchestrator,
dispatching a multi-step task with the 4-tuple composite identity, executing
sandboxed work, and gracefully shutting down the platform.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.control_plane.main import app as control_plane_app
from src.control_plane.schemas import AgentCompositeKey
from src.orchestrator.registry import default_registry


@pytest.mark.unauthenticated
@pytest.mark.asyncio
async def test_deploy_mock_agent_execute_and_shutdown():
    """Complete lifecycle: Deploy agent spec -> Run task -> Verify telemetry & artifacts -> Teardown."""
    # 1. Setup composite 4-tuple identity
    composite_key = AgentCompositeKey(
        actor_id="actor-tester-01",
        agent_id="mock-silicon-agent",
        cost_centre_id="cc-hardware-eval",
        session_id="sess-e2e-lifecycle-42",
    )

    custom_headers = {
        "X-User-ID": composite_key.actor_id,
        "X-User-Role": "admin",
        "X-User-Scopes": "llm:proxy,tools:register,tools:execute",
        "X-Actor-ID": composite_key.actor_id,
        "X-Agent-ID": composite_key.agent_id,
        "X-Cost-Centre-ID": composite_key.cost_centre_id,
        "X-Session-ID": composite_key.session_id,
        "X-Aegis-URN": composite_key.urn,
    }

    async with AsyncClient(
        transport=ASGITransport(app=control_plane_app),
        base_url="http://control-plane:8000",
        headers=custom_headers,
    ) as client:
        # Step 1: Health check - platform ready
        health_res = await client.get("/health")
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "healthy"

        # Step 2: Deploy mock agent manifest into orchestrator
        agent_spec_payload = {
            "agent_id": composite_key.agent_id,
            "name": "Mock Silicon Optimizer",
            "description": "Analyzes roofline intensity and executes hardware benchmarks",
            "topology": "STANDALONE",
            "model": "gpt-4o",
            "system_prompt": "You are a hardware performance optimizer.",
            "allowed_tools": ["get_accelerator_specs", "execute_code"],
            "sub_agents": [],
            "max_steps": 5,
            "timeout_seconds": 30.0,
        }

        deploy_res = await client.post("/api/v1/orchestrator/specs", json=agent_spec_payload)
        assert deploy_res.status_code == 201
        assert deploy_res.json()["agent_id"] == composite_key.agent_id

        # Verify deployment listed in catalog
        list_res = await client.get("/api/v1/orchestrator/specs")
        assert list_res.status_code == 200
        assert any(spec["agent_id"] == composite_key.agent_id for spec in list_res.json())

        # Step 3: Trigger agent execution run
        run_payload = {
            "prompt": "Evaluate roofline arithmetic intensity for matrix multiply on vortex-npu-v2",
            "context": {"matrix_dim": 1024, "data_type": "float32"},
        }

        run_res = await client.post(
            f"/api/v1/orchestrator/runs/{composite_key.agent_id}",
            json=run_payload,
        )
        assert run_res.status_code == 200
        run_data = run_res.json()
        assert run_data["status"] == "COMPLETED"
        assert run_data["session_id"] == composite_key.session_id
        assert run_data["composite_key"]["actor_id"] == composite_key.actor_id
        assert run_data["composite_key"]["agent_id"] == composite_key.agent_id
        assert run_data["composite_key"]["cost_centre_id"] == composite_key.cost_centre_id
        assert run_data["composite_key"]["session_id"] == composite_key.session_id
        assert len(run_data["history"]) > 0

        # Step 4: Verify session state and artifacts
        session_res = await client.get(
            f"/api/v1/orchestrator/sessions/{composite_key.session_id}"
        )
        assert session_res.status_code == 200
        session_state = session_res.json()
        assert session_state["status"] == "COMPLETED"
        assert session_state["current_step"] == len(session_state["history"])
        assert "Successfully processed prompt" in session_state["output"]

        # Step 5: Test graceful cancellation / cleanup on active session
        cancel_res = await client.post(
            f"/api/v1/orchestrator/sessions/{composite_key.session_id}/cancel"
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "CANCELLED"

        # Step 6: Teardown / Undeploy agent from orchestrator
        unregistered = default_registry.unregister(composite_key.agent_id)
        assert unregistered is True

        # Verify agent is purged from catalog
        specs_post_teardown = await client.get("/api/v1/orchestrator/specs")
        assert not any(
            spec["agent_id"] == composite_key.agent_id for spec in specs_post_teardown.json()
        )
