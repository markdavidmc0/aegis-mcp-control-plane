"""MCP Gateway Router (JSON-RPC Gateway).

Routes /mcp tool calls and tool lists directly to the Data Plane execution sandbox.
"""

import logging

import httpx
import logfire
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from src.control_plane.dependencies import get_data_plane_client, get_user_context
from src.control_plane.policy_engine import OPAPolicyEngine
from src.control_plane.schemas import (
    JSONRPCError,
    MCPJsonRPCRequest,
    MCPJsonRPCResponse,
    UserContext,
)

logger = logging.getLogger("mvcp.mcp_router")
router = APIRouter(tags=["MCP Gateway Router"])
policy_engine = OPAPolicyEngine()



@router.post("/mcp", response_model=MCPJsonRPCResponse)
@router.post("/api/v1/mcp", response_model=MCPJsonRPCResponse)
async def handle_mcp_request(
    request: MCPJsonRPCRequest,
    user: UserContext = Depends(get_user_context),
    data_plane: httpx.AsyncClient = Depends(get_data_plane_client),
) -> JSONResponse:
    """Proxies MCP requests to the Data Plane with identity propagation."""
    forwarded_headers = {
        "X-User-ID": user.user_id,
        "X-User-Role": user.role,
        "X-User-Scopes": ",".join(user.scopes),
    }

    if user.composite_key:
        forwarded_headers["X-Actor-ID"] = user.composite_key.actor_id
        forwarded_headers["X-Agent-ID"] = user.composite_key.agent_id
        forwarded_headers["X-Cost-Centre-ID"] = user.composite_key.cost_centre_id
        forwarded_headers["X-Session-ID"] = user.composite_key.session_id
        forwarded_headers["X-Aegis-URN"] = user.composite_key.urn

    urn = user.composite_key.urn if user.composite_key else None

    # OPA/Rego Policy Compliance Evaluation
    if request.method == "tools/call":
        tool_name = request.params.get("name", "")
        tool_args = request.params.get("arguments", {})
        decision = policy_engine.evaluate_tool_execution(tool_name, tool_args, user)
        if not decision.allowed:
            violation_msg = (
                f"Policy violation: {'; '.join(decision.violations)}"
                if decision.violations
                else "Policy violation: tool execution denied by policy engine."
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=MCPJsonRPCResponse(
                    id=request.id,
                    error=JSONRPCError(
                        code=-32000,
                        message=violation_msg,
                        data={"violations": decision.violations, "rule": decision.rule},
                    ),
                ).model_dump(exclude_none=True),
            )

    with logfire.span(
        "mcp_router.forward_request",
        method=request.method,
        user_id=user.user_id,
        urn=urn,
    ):
        try:
            response = await data_plane.post(
                "/api/v1/mcp",
                json=request.model_dump(exclude_none=True),
                headers=forwarded_headers,
            )
            return JSONResponse(status_code=response.status_code, content=response.json())

        except httpx.HTTPStatusError as err:
            logger.error(f"[MCP Gateway] Data plane HTTP error: {err}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=MCPJsonRPCResponse(
                    id=request.id,
                    error=JSONRPCError(
                        code=-32603,
                        message=f"Data Plane execution HTTP error: {err.response.text}",
                    ),
                ).model_dump(exclude_none=True),
            )
        except Exception as err:
            logger.error(f"[MCP Gateway] Failed communicating with Data Plane: {err}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=MCPJsonRPCResponse(
                    id=request.id,
                    error=JSONRPCError(
                        code=-32603,
                        message=f"Data Plane sandbox unreachable: {str(err)}",
                    ),
                ).model_dump(exclude_none=True),
            )
