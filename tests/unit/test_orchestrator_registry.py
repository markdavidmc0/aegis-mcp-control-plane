import pytest

from src.orchestrator.registry import AgentRegistry
from src.orchestrator.schemas import AgentSpec, AgentTopology


@pytest.fixture
def sample_spec() -> AgentSpec:
    """Fixture for a sample AgentSpec."""
    return AgentSpec(
        agent_id="test-agent-1",
        name="Test Agent One",
        description="First test agent",
        topology=AgentTopology.STANDALONE,
        system_prompt="Prompt 1",
    )


@pytest.fixture
def supervisor_spec() -> AgentSpec:
    """Fixture for a supervisor AgentSpec."""
    return AgentSpec(
        agent_id="supervisor-agent",
        name="Supervisor Agent",
        description="Coordinates sub-agents",
        topology=AgentTopology.SUPERVISOR,
        system_prompt="Supervisor prompt",
        sub_agents=["worker-agent"],
    )


@pytest.mark.unit
def test_agent_registry_register_and_get(sample_spec: AgentSpec):
    """Test registering and retrieving an agent spec."""
    registry = AgentRegistry()
    registry.register(sample_spec)

    retrieved = registry.get("test-agent-1")
    assert retrieved == sample_spec

    # Unknown agent returns None
    assert registry.get("non-existent") is None


@pytest.mark.unit
def test_agent_registry_list(sample_spec: AgentSpec, supervisor_spec: AgentSpec):
    """Test listing all registered agent specs."""
    registry = AgentRegistry()
    assert registry.list() == []

    registry.register(sample_spec)
    registry.register(supervisor_spec)

    specs = registry.list()
    assert len(specs) == 2
    assert sample_spec in specs
    assert supervisor_spec in specs


@pytest.mark.unit
def test_agent_registry_unregister(sample_spec: AgentSpec):
    """Test unregistering an agent spec."""
    registry = AgentRegistry()
    registry.register(sample_spec)
    assert registry.get("test-agent-1") is not None

    removed = registry.unregister("test-agent-1")
    assert removed is True
    assert registry.get("test-agent-1") is None

    # Unregistering non-existent returns False
    assert registry.unregister("test-agent-1") is False


@pytest.mark.unit
def test_agent_registry_overwrite(sample_spec: AgentSpec):
    """Test re-registering an agent spec overwrites existing spec."""
    registry = AgentRegistry()
    registry.register(sample_spec)

    updated_spec = AgentSpec(
        agent_id="test-agent-1",
        name="Test Agent Updated",
        description="Updated description",
        topology=AgentTopology.STANDALONE,
        system_prompt="Updated prompt",
    )
    registry.register(updated_spec)
    retrieved = registry.get("test-agent-1")
    assert retrieved is not None
    assert retrieved.name == "Test Agent Updated"
