import pytest

from src.control_plane.schemas import AgentCompositeKey
from src.orchestrator.registry import AgentRegistry
from src.orchestrator.runtime import AgentRuntimeOrchestrator
from src.orchestrator.schemas import (
    AgentExecutionStatus,
    AgentHandoffRequest,
    AgentRunRequest,
    AgentSpec,
    AgentTopology,
)


@pytest.fixture
def registry() -> AgentRegistry:
    """Fixture providing populated agent registry."""
    reg = AgentRegistry()
    reg.register(
        AgentSpec(
            agent_id="worker-1",
            name="Worker One",
            description="Executes sub tasks",
            topology=AgentTopology.WORKER,
            system_prompt="You are a dedicated worker.",
            allowed_tools=["calculator"],
        )
    )
    reg.register(
        AgentSpec(
            agent_id="supervisor-1",
            name="Supervisor One",
            description="Coordinates worker tasks",
            topology=AgentTopology.SUPERVISOR,
            system_prompt="You are a supervisor agent.",
            sub_agents=["worker-1"],
        )
    )
    reg.register(
        AgentSpec(
            agent_id="standalone-1",
            name="Standalone One",
            description="Standalone execution",
            topology=AgentTopology.STANDALONE,
            system_prompt="You are a standalone agent.",
        )
    )
    return reg


@pytest.fixture
def base_composite_key() -> AgentCompositeKey:
    """Fixture providing sample caller identity key."""
    return AgentCompositeKey(
        actor_id="actor-alice",
        agent_id="supervisor-1",
        cost_centre_id="eng-cc-99",
        session_id="session-root-123",
    )


@pytest.mark.integration
async def test_agent_runtime_standalone_run(registry: AgentRegistry, base_composite_key: AgentCompositeKey):
    """Verify standalone agent executes and records step history."""
    orchestrator = AgentRuntimeOrchestrator(registry=registry)

    standalone_key = AgentCompositeKey(
        actor_id=base_composite_key.actor_id,
        agent_id="standalone-1",
        cost_centre_id=base_composite_key.cost_centre_id,
        session_id="session-standalone-1",
    )

    request = AgentRunRequest(prompt="Analyze system logs", context={"depth": "shallow"})
    session_state = await orchestrator.run(key=standalone_key, request=request)

    assert session_state.status == AgentExecutionStatus.COMPLETED
    assert session_state.session_id == "session-standalone-1"
    assert session_state.composite_key.urn == standalone_key.urn
    assert len(session_state.history) > 0
    assert session_state.output is not None

    # Retrieve by session ID
    retrieved = orchestrator.get_session("session-standalone-1")
    assert retrieved == session_state


@pytest.mark.integration
async def test_agent_runtime_delegation_preserves_actor_and_cost_centre(
    registry: AgentRegistry, base_composite_key: AgentCompositeKey
):
    """Verify supervisor can delegate to allowed worker, strictly preserving actor_id and cost_centre_id."""
    orchestrator = AgentRuntimeOrchestrator(registry=registry)

    handoff = AgentHandoffRequest(
        parent_session_id=base_composite_key.session_id,
        caller_agent_id="supervisor-1",
        target_agent_id="worker-1",
        task_instructions="Perform numeric calculation",
        context_data={"expression": "2 + 2"},
    )

    worker_session = await orchestrator.handoff(
        parent_key=base_composite_key,
        handoff=handoff,
    )

    assert worker_session.status == AgentExecutionStatus.COMPLETED
    # Strictly preserve actor_id and cost_centre_id
    assert worker_session.composite_key.actor_id == base_composite_key.actor_id
    assert worker_session.composite_key.cost_centre_id == base_composite_key.cost_centre_id
    assert worker_session.composite_key.agent_id == "worker-1"
    assert worker_session.composite_key.session_id.startswith(f"{base_composite_key.session_id}-worker-1-")


@pytest.mark.integration
async def test_agent_runtime_unauthorized_delegation_rejected(
    registry: AgentRegistry, base_composite_key: AgentCompositeKey
):
    """Verify delegation to an agent NOT in supervisor sub_agents is rejected."""
    orchestrator = AgentRuntimeOrchestrator(registry=registry)

    handoff = AgentHandoffRequest(
        parent_session_id=base_composite_key.session_id,
        caller_agent_id="supervisor-1",
        target_agent_id="standalone-1",  # Not in supervisor-1.sub_agents
        task_instructions="Perform unauthorized task",
    )

    with pytest.raises(ValueError, match="not an authorized sub-agent"):
        await orchestrator.handoff(
            parent_key=base_composite_key,
            handoff=handoff,
        )


@pytest.mark.integration
async def test_agent_runtime_cancel_session(registry: AgentRegistry, base_composite_key: AgentCompositeKey):
    """Verify session can be cancelled."""
    orchestrator = AgentRuntimeOrchestrator(registry=registry)

    key = AgentCompositeKey(
        actor_id=base_composite_key.actor_id,
        agent_id="standalone-1",
        cost_centre_id=base_composite_key.cost_centre_id,
        session_id="session-to-cancel",
    )

    # Pre-create or run
    await orchestrator.run(key=key, request=AgentRunRequest(prompt="Run before cancel"))
    cancelled_session = orchestrator.cancel_session("session-to-cancel")
    assert cancelled_session is not None
    assert cancelled_session.status == AgentExecutionStatus.CANCELLED
