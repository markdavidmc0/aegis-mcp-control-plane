"""Data Plane Pydantic Schemas & MCP Protocol Specifications."""

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


class DataPlaneUserContext(BaseModel):
    """User context container injected via downstream HTTP headers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(..., min_length=1, description="Unique user identifier")
    role: str = Field(default="user", min_length=1)
    scopes: list[str] = Field(default_factory=list)
    protocol_version: str = Field(default="2026-07-28", min_length=1)
    composite_key: AgentCompositeKey | None = None


class DataPlaneHealthResponse(BaseModel):
    """Execution worker health status response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(default="healthy", min_length=1)
    service: str = Field(default="data-plane", min_length=1)
    engine: str = Field(default="gvisor_monty", min_length=1)


class DataPlaneJSONRPCError(BaseModel):
    """JSON-RPC 2.0 Error model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: int
    message: str
    data: Any | None = None


class DataPlaneJSONRPCRequest(BaseModel):
    """Incoming MCP JSON-RPC 2.0 Request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    method: str = Field(..., min_length=1, description="e.g., 'tools/list', 'tools/call'")
    params: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] | None = Field(default=None, alias="_meta")


class DataPlaneJSONRPCResponse(BaseModel):
    """Outgoing MCP JSON-RPC 2.0 Response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: Any | None = None
    error: DataPlaneJSONRPCError | None = None


class ServerCapabilities(BaseModel):
    """Capabilities supported by the Data Plane FastMCP server."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tools: dict[str, Any] = Field(default_factory=dict)
    resources: dict[str, Any] = Field(default_factory=dict)
    prompts: dict[str, Any] = Field(default_factory=dict)


class ServerDiscoverResult(BaseModel):
    """Response payload for stateless 'server/discover' method."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)

    protocol_versions: list[str] = Field(
        default_factory=lambda: ["2026-07-28", "2025-11-25"],
        alias="protocolVersions",
    )
    capabilities: ServerCapabilities = Field(default_factory=ServerCapabilities)
    server_info: dict[str, Any] = Field(
        default_factory=lambda: {"name": "data-plane-mcp", "version": "0.1.0"},
        alias="serverInfo",
    )


# Standard MCP Tool Definitions
EXECUTE_CODE_TOOL_SCHEMA = {
    "name": "execute_code",
    "description": "Executes sandboxed Python code within the isolated Data Plane environment.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code block to execute in the sandbox.",
            },
            "inputs": {
                "type": "object",
                "description": "Optional key-value variable bindings.",
            },
        },
        "required": ["code"],
    },
}
