import pytest
from pydantic import ValidationError

from src.control_plane.schemas import AgentCompositeKey
from src.orchestrator.schemas import (
    AgentExecutionStatus,
    AgentHandoffRequest,
    AgentRunRequest,
    AgentSessionState,
    AgentSpec,
    AgentStepArtifact,
    AgentTopology,
)


@pytest.mark.unit
def test_agent_topology_enum():
    """Verify AgentTopology values."""
    assert AgentTopology.STANDALONE == "STANDALONE"
    assert AgentTopology.SUPERVISOR == "SUPERVISOR"
    assert AgentTopology.WORKER == "WORKER"


@pytest.mark.unit
def test_agent_execution_status_enum():
    """Verify AgentExecutionStatus values."""
    assert AgentExecutionStatus.PENDING == "PENDING"
    assert AgentExecutionStatus.RUNNING == "RUNNING"
    assert AgentExecutionStatus.PAUSED_AWAITING_HUMAN == "PAUSED_AWAITING_HUMAN"
    assert AgentExecutionStatus.COMPLETED == "COMPLETED"
    assert AgentExecutionStatus.FAILED == "FAILED"
    assert AgentExecutionStatus.CANCELLED == "CANCELLED"


@pytest.mark.unit
def test_agent_spec_defaults_and_validation():
    """Verify AgentSpec validation and defaults."""
    spec = AgentSpec(
        agent_id="test-agent",
        name="Test Agent",
        description="A test agent",
        topology=AgentTopology.STANDALONE,
        system_prompt="You are a test agent.",
    )
    assert spec.model == "gpt-4o"
    assert spec.allowed_tools == []
    assert spec.sub_agents == []
    assert spec.max_steps == 15
    assert spec.timeout_seconds == 120.0

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        AgentSpec(
            agent_id="test-agent",
            name="Test Agent",
            description="A test agent",
            topology=AgentTopology.STANDALONE,
            system_prompt="You are a test agent.",
            unknown_field="fail",  # type: ignore
        )


@pytest.mark.unit
def test_agent_step_artifact():
    """Verify AgentStepArtifact fields and immutability."""
    artifact = AgentStepArtifact(
        step_number=1,
        agent_id="test-agent",
        thought="Processing task...",
        tool_call_name="execute_code",
        tool_arguments={"code": "print(1)"},
        tool_output="1",
        code_executed="print(1)",
    )
    assert artifact.step_number == 1
    assert artifact.tool_call_name == "execute_code"

    # Frozen
    with pytest.raises(ValidationError):
        artifact.thought = "New thought"  # type: ignore


@pytest.mark.unit
def test_agent_session_state():
    """Verify AgentSessionState initialization and defaults."""
    key = AgentCompositeKey(
        actor_id="user1",
        agent_id="agent1",
        cost_centre_id="cc1",
        session_id="sess1",
    )
    state = AgentSessionState(
        session_id="sess1",
        composite_key=key,
    )
    assert state.status == AgentExecutionStatus.PENDING
    assert state.current_step == 0
    assert state.history == []
    assert state.output is None
    assert state.error is None


@pytest.mark.unit
def test_agent_run_request_and_handoff_request():
    """Verify AgentRunRequest and AgentHandoffRequest schema contracts."""
    run_req = AgentRunRequest(prompt="Analyze data", context={"key": "val"})
    assert run_req.prompt == "Analyze data"
    assert run_req.context == {"key": "val"}

    handoff = AgentHandoffRequest(
        parent_session_id="sess-parent",
        caller_agent_id="supervisor-1",
        target_agent_id="worker-1",
        task_instructions="Perform calculation",
        context_data={"num": 42},
    )
    assert handoff.caller_agent_id == "supervisor-1"
    assert handoff.target_agent_id == "worker-1"
