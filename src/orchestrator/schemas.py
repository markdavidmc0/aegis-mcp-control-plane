"""Orchestrator domain contracts and strict types."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.control_plane.schemas import AgentCompositeKey


class AgentTopology(StrEnum):
    """Execution topology configuration of an agent."""

    STANDALONE = "STANDALONE"
    SUPERVISOR = "SUPERVISOR"
    WORKER = "WORKER"


class AgentExecutionStatus(StrEnum):
    """Runtime execution state of an agent session."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED_AWAITING_HUMAN = "PAUSED_AWAITING_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentSpec(BaseModel):
    """Static declarative specification for an orchestrator agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_id: str = Field(..., min_length=1, description="Unique agent identifier")
    name: str = Field(..., min_length=1, description="Human readable agent name")
    description: str = Field(..., min_length=1, description="Purpose and scope of agent")
    topology: AgentTopology = Field(..., description="Agent structural topology")
    model: str = Field(default="gpt-4o", min_length=1, description="Underlying LLM model identifier")
    system_prompt: str = Field(..., min_length=1, description="Core system instructions")
    allowed_tools: list[str] = Field(default_factory=list, description="Permitted tool names")
    sub_agents: list[str] = Field(default_factory=list, description="Sub-agent IDs delegatable by supervisor")
    max_steps: int = Field(default=15, ge=1, le=100, description="Step count ceiling")
    timeout_seconds: float = Field(default=120.0, gt=0.0, le=3600.0, description="Execution timeout limit")


class AgentStepArtifact(BaseModel):
    """Immutable trace artifact representing a single step within an execution loop."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_number: int = Field(..., ge=1, description="Sequence index of the step")
    agent_id: str = Field(..., min_length=1, description="Agent performing the step")
    thought: str = Field(default="", description="Internal chain-of-thought rationale")
    tool_call_name: str | None = Field(default=None, description="Name of tool invoked, if any")
    tool_arguments: dict[str, Any] | None = Field(default=None, description="Arguments supplied to tool")
    tool_output: Any | None = Field(default=None, description="Result returned by tool execution")
    code_executed: str | None = Field(default=None, description="Dynamic code executed, if applicable")


class AgentSessionState(BaseModel):
    """Current state and execution trace of an agent session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str = Field(..., min_length=1, description="Session identifier")
    composite_key: AgentCompositeKey = Field(..., description="Aegis 4-tuple identity key")
    status: AgentExecutionStatus = Field(default=AgentExecutionStatus.PENDING, description="Current execution state")
    current_step: int = Field(default=0, ge=0, description="Current execution step index")
    history: list[AgentStepArtifact] = Field(default_factory=list, description="Ordered step execution history")
    output: Any | None = Field(default=None, description="Final agent output on completion")
    error: str | None = Field(default=None, description="Failure reason if status is FAILED")


class AgentRunRequest(BaseModel):
    """Payload to initiate an agent run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str = Field(..., min_length=1, description="User or supervisor instructions")
    context: dict[str, Any] = Field(default_factory=dict, description="Execution context metadata")


class AgentHandoffRequest(BaseModel):
    """Payload for delegation from supervisor to worker sub-agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_session_id: str = Field(..., min_length=1, description="Originating supervisor session ID")
    caller_agent_id: str = Field(..., min_length=1, description="Supervisor agent identifier")
    target_agent_id: str = Field(..., min_length=1, description="Worker agent identifier")
    task_instructions: str = Field(..., min_length=1, description="Specific sub-task instructions")
    context_data: dict[str, Any] = Field(default_factory=dict, description="Context propagated to sub-agent")
