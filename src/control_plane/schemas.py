"""Control Plane Pydantic Schemas & Types."""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_KEY_IDENTIFIER_PATTERN = r"^[a-zA-Z0-9_\-]+$"
_KEY_IDENTIFIER_REGEX = re.compile(_KEY_IDENTIFIER_PATTERN)


class AgentCompositeKey(BaseModel):
    """4-Tuple Identity & Context Backbone for agent requests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(..., min_length=1, pattern=_KEY_IDENTIFIER_PATTERN)
    agent_id: str = Field(..., min_length=1, pattern=_KEY_IDENTIFIER_PATTERN)
    cost_centre_id: str = Field(..., min_length=1, pattern=_KEY_IDENTIFIER_PATTERN)
    session_id: str = Field(..., min_length=1, pattern=_KEY_IDENTIFIER_PATTERN)

    @property
    def urn(self) -> str:
        """Construct canonical Aegis URN representation."""
        return f"urn:aegis:agent:{self.actor_id}:{self.agent_id}:{self.cost_centre_id}:{self.session_id}"

    @classmethod
    def from_urn(cls, urn: str) -> "AgentCompositeKey":
        """Parse AgentCompositeKey from canonical Aegis URN."""
        parts = urn.split(":")
        if len(parts) != 7 or parts[0] != "urn" or parts[1] != "aegis" or parts[2] != "agent":
            raise ValueError(f"Invalid Aegis URN format: {urn}")

        actor_id, agent_id, cost_centre_id, session_id = parts[3], parts[4], parts[5], parts[6]
        for val, name in (
            (actor_id, "actor_id"),
            (agent_id, "agent_id"),
            (cost_centre_id, "cost_centre_id"),
            (session_id, "session_id"),
        ):
            if not _KEY_IDENTIFIER_REGEX.match(val):
                raise ValueError(f"Invalid characters in {name}: {val}")

        return cls(
            actor_id=actor_id,
            agent_id=agent_id,
            cost_centre_id=cost_centre_id,
            session_id=session_id,
        )


class UserContext(BaseModel):
    """Authenticated user context injected by upstream Envoy / API Gateway."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(..., min_length=1, description="Unique subject ID")
    role: str = Field(default="user", min_length=1)
    scopes: list[str] = Field(default_factory=list)
    composite_key: AgentCompositeKey | None = None


class JSONRPCError(BaseModel):
    """Standard JSON-RPC 2.0 Error payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: int
    message: str
    data: Any | None = None


class MCPJsonRPCRequest(BaseModel):
    """Incoming JSON-RPC 2.0 request for /mcp endpoints."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    method: str = Field(..., min_length=1, description="e.g. 'tools/list' or 'tools/call'")
    params: dict[str, Any] = Field(default_factory=dict)


class MCPJsonRPCResponse(BaseModel):
    """Outgoing JSON-RPC 2.0 response from /mcp endpoints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: Any | None = None
    error: JSONRPCError | None = None


class ToolRegistrationSchema(BaseModel):
    """Payload schema for registering tools into catalog.json."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(..., min_length=1, description="Unique tool identifier")
    description: str = Field(..., min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    entrypoint: str | None = None


class ControlPlaneHealthResponse(BaseModel):
    """Health readiness response schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(default="healthy", min_length=1)
    identity_layer: str = Field(default="keycloak_wif", min_length=1)


class ToolStubResponse(BaseModel):
    """Response containing a single generated Python tool stub."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str = Field(..., min_length=1, description="Unique tool identifier")
    stub: str = Field(..., description="Generated Python function stub")


class CatalogStubsResponse(BaseModel):
    """Response containing combined Python stubs and metadata for catalog tools."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stubs: str = Field(..., description="Combined Python stubs for all tools")
    tools: list[str] = Field(..., description="List of included tool names")


class ModelFailoverPolicy(BaseModel):
    """Failover policy configuration for upstream LLM routing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_model: str = "gemini-3.8-flash-8192"
    fallback_tiers: list[str] = Field(
        default_factory=lambda: ["gemini-3.8-flash-32768", "gpt-4o"]
    )
    max_retries_per_tier: int = Field(default=2, ge=1, le=5)
    retryable_status_codes: list[int] = Field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )
    backoff_factor: float = Field(default=0.5, ge=0.0, le=5.0)


class PolicyDecision(BaseModel):
    """OPA/Rego policy evaluation decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool = Field(..., description="Whether action is permitted")
    rule: str = Field(..., description="Evaluating policy rule identifier")
    violations: list[str] = Field(
        default_factory=list, description="Reason(s) for denial"
    )



