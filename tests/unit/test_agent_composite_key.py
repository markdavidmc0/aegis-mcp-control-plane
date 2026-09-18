"""Unit tests for AgentCompositeKey domain model and 4-tuple identity."""

import pytest
from pydantic import ValidationError

from src.control_plane.schemas import AgentCompositeKey as ControlPlaneCompositeKey
from src.data_plane.schemas import AgentCompositeKey as DataPlaneCompositeKey


@pytest.mark.unit
@pytest.mark.parametrize("model_cls", [ControlPlaneCompositeKey, DataPlaneCompositeKey])
def test_agent_composite_key_valid_construction(model_cls):
    """Verify valid construction with alphanumeric, underscore, and hyphen characters."""
    key = model_cls(
        actor_id="user_123",
        agent_id="agent-coder-v1",
        cost_centre_id="cc_engineering-42",
        session_id="sess_abc-xyz_01",
    )
    assert key.actor_id == "user_123"
    assert key.agent_id == "agent-coder-v1"
    assert key.cost_centre_id == "cc_engineering-42"
    assert key.session_id == "sess_abc-xyz_01"


@pytest.mark.unit
@pytest.mark.parametrize("model_cls", [ControlPlaneCompositeKey, DataPlaneCompositeKey])
def test_agent_composite_key_urn_generation(model_cls):
    """Verify urn property generates correct URN format."""
    key = model_cls(
        actor_id="usr-99",
        agent_id="bot-42",
        cost_centre_id="fin-ops",
        session_id="sess-001",
    )
    expected_urn = "urn:aegis:agent:usr-99:bot-42:fin-ops:sess-001"
    assert key.urn == expected_urn


@pytest.mark.unit
@pytest.mark.parametrize("model_cls", [ControlPlaneCompositeKey, DataPlaneCompositeKey])
def test_agent_composite_key_from_urn_roundtrip(model_cls):
    """Verify parsing valid URN returns identical AgentCompositeKey."""
    urn = "urn:aegis:agent:actor_1:agent_2:cc_3:sess_4"
    key = model_cls.from_urn(urn)
    assert key.actor_id == "actor_1"
    assert key.agent_id == "agent_2"
    assert key.cost_centre_id == "cc_3"
    assert key.session_id == "sess_4"
    assert key.urn == urn


@pytest.mark.unit
@pytest.mark.parametrize("model_cls", [ControlPlaneCompositeKey, DataPlaneCompositeKey])
@pytest.mark.parametrize(
    "invalid_urn",
    [
        "",
        "invalid-urn",
        "urn:aegis:agent:too:few:parts",
        "urn:aegis:agent:too:many:parts:extra:item",
        "urn:other:agent:a:b:c:d",
        "urn:aegis:other:a:b:c:d",
        "urn:aegis:agent::b:c:d",
        "urn:aegis:agent:a::c:d",
        "urn:aegis:agent:a:b::d",
        "urn:aegis:agent:a:b:c:",
        "urn:aegis:agent:a@bad:b:c:d",
    ],
)
def test_agent_composite_key_from_urn_invalid(model_cls, invalid_urn):
    """Verify from_urn raises ValueError for invalid URN formats."""
    with pytest.raises(ValueError):
        model_cls.from_urn(invalid_urn)


@pytest.mark.unit
@pytest.mark.parametrize("model_cls", [ControlPlaneCompositeKey, DataPlaneCompositeKey])
@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("actor_id", ""),
        ("actor_id", "bad actor"),
        ("actor_id", "bad:actor"),
        ("actor_id", "bad/actor"),
        ("agent_id", ""),
        ("agent_id", "agent@id"),
        ("cost_centre_id", ""),
        ("cost_centre_id", "cc#1"),
        ("session_id", ""),
        ("session_id", "sess!"),
    ],
)
def test_agent_composite_key_invalid_field_patterns(model_cls, field, bad_value):
    """Verify field constraints enforce min_length=1 and pattern matching."""
    valid_args = {
        "actor_id": "valid_actor",
        "agent_id": "valid_agent",
        "cost_centre_id": "valid_cc",
        "session_id": "valid_sess",
    }
    valid_args[field] = bad_value
    with pytest.raises(ValidationError):
        model_cls(**valid_args)


@pytest.mark.unit
@pytest.mark.parametrize("model_cls", [ControlPlaneCompositeKey, DataPlaneCompositeKey])
def test_agent_composite_key_immutability(model_cls):
    """Verify frozen=True prevents mutation and extra='forbid' prevents extra fields."""
    key = model_cls(
        actor_id="actor",
        agent_id="agent",
        cost_centre_id="cc",
        session_id="sess",
    )
    with pytest.raises(ValidationError):
        key.actor_id = "new_actor"

    with pytest.raises(ValidationError):
        model_cls(
            actor_id="actor",
            agent_id="agent",
            cost_centre_id="cc",
            session_id="sess",
            extra_field="disallowed",
        )
