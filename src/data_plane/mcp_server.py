"""FastMCP / JSON-RPC 2.0 Execution Server."""

import contextlib
import io
import logging
from typing import Any

import logfire
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from src.data_plane.context import user_context_var
from src.data_plane.dependencies import (
    data_plane_lifespan,
    get_tool_dispatcher,
    get_user_context,
)
from src.data_plane.schemas import (
    AgentCompositeKey,
    DataPlaneHealthResponse,
    DataPlaneJSONRPCError,
    DataPlaneJSONRPCRequest,
    DataPlaneJSONRPCResponse,
    DataPlaneUserContext,
    ServerDiscoverResult,
)
from src.data_plane.worker import LocalToolDispatcher

logger = logging.getLogger("mvcp.data_plane")

app = FastAPI(
    title="Data Plane FastMCP Server",
    description="gVisor Sandboxed FastMCP Execution Engine",
    version="1.0.0",
    lifespan=data_plane_lifespan,
)

# Pydantic Logfire Instrumentation
logfire.configure(
    service_name="aegis-data-plane",
    inspect_arguments=False,
)
logfire.instrument_fastapi(app)
logfire.instrument_pydantic()


class CodeExecutionRequest(BaseModel):
    """Payload container for sandboxed code execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(..., min_length=1, description="Python code block to execute")


@app.get("/health", response_model=DataPlaneHealthResponse)
@app.get("/api/v1/health", response_model=DataPlaneHealthResponse)
async def health_check() -> DataPlaneHealthResponse:
    """Return health status of the execution worker and sandbox engine."""
    return DataPlaneHealthResponse(status="healthy", service="data-plane", engine="gvisor_monty")


@app.middleware("http")
async def extract_identity_middleware(request: Request, call_next: Any) -> Response:
    """Propagates upstream user context into task-isolated contextvars."""
    if request.url.path in ("/health", "/api/v1/health"):
        return await call_next(request)

    actor_id = request.headers.get("X-Actor-ID")
    user_id = request.headers.get("X-User-ID")
    effective_user_id = actor_id or user_id
    if not effective_user_id:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing required header: X-User-ID"},
        )

    urn = request.headers.get("X-Aegis-URN")
    composite_key: AgentCompositeKey | None = None
    if urn:
        try:
            composite_key = AgentCompositeKey.from_urn(urn)
        except Exception:
            composite_key = None

    if not composite_key:
        actor = actor_id or user_id
        agent = request.headers.get("X-Agent-ID", "default-agent")
        cost_centre = request.headers.get("X-Cost-Centre-ID", "default-cost-centre")
        session = request.headers.get("X-Session-ID", "default-session")
        try:
            composite_key = AgentCompositeKey(
                actor_id=actor,
                agent_id=agent,
                cost_centre_id=cost_centre,
                session_id=session,
            )
        except Exception:
            composite_key = None

    scopes = [s.strip() for s in request.headers.get("X-User-Scopes", "").split(",") if s.strip()]
    ctx = DataPlaneUserContext(
        user_id=effective_user_id,
        role=request.headers.get("X-User-Role", "user"),
        scopes=scopes,
        composite_key=composite_key,
    )

    token = user_context_var.set(ctx)
    try:
        return await call_next(request)
    finally:
        user_context_var.reset(token)


@app.post("/api/v1/sandbox/execute")
async def execute_in_sandbox(
    req: CodeExecutionRequest,
    dispatcher: LocalToolDispatcher = Depends(get_tool_dispatcher),
    user_context: DataPlaneUserContext | None = Depends(get_user_context),
) -> JSONResponse:
    """Executes raw Python snippets within REPL scope."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            exec_globals = {"__name__": "__main__"}
            exec(req.code, exec_globals)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "SUCCESS",
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr_buf.getvalue(),
            },
        )
    except Exception as err:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "FAILED", "error": str(err), "stderr": stderr_buf.getvalue()},
        )


@app.post("/api/v1/mcp", response_model=DataPlaneJSONRPCResponse)
async def handle_mcp_jsonrpc(
    request: DataPlaneJSONRPCRequest,
    dispatcher: LocalToolDispatcher = Depends(get_tool_dispatcher),
    user_context: DataPlaneUserContext | None = Depends(get_user_context),
) -> JSONResponse:
    """Handles incoming JSON-RPC 2.0 requests over network boundary."""
    req_id = request.id
    method = request.method

    try:
        if method in ("server/discover", "initialize"):
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=DataPlaneJSONRPCResponse(
                    id=req_id, result=ServerDiscoverResult().model_dump(by_alias=True)
                ).model_dump(exclude_none=True),
            )

        if method == "tools/list":
            tools = await dispatcher.read_catalog()
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=DataPlaneJSONRPCResponse(id=req_id, result={"tools": tools}).model_dump(
                    exclude_none=True
                ),
            )

        if method == "tools/call":
            params = request.params or {}
            tool_name = params.get("name") or params.get("tool_name")
            arguments = params.get("arguments") or {}

            if not tool_name:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=DataPlaneJSONRPCResponse(
                        id=req_id,
                        error=DataPlaneJSONRPCError(code=-32602, message="Tool name required"),
                    ).model_dump(exclude_none=True),
                )

            res = await dispatcher.dispatch_tool_call(
                tool_name, arguments, user_context=user_context
            )
            if isinstance(res, dict):
                res["id"] = req_id
                if "jsonrpc" not in res:
                    res["jsonrpc"] = "2.0"
                return JSONResponse(status_code=status.HTTP_200_OK, content=res)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=DataPlaneJSONRPCResponse(id=req_id, result=res).model_dump(exclude_none=True),
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=DataPlaneJSONRPCResponse(
                id=req_id,
                error=DataPlaneJSONRPCError(code=-32601, message=f"Method '{method}' not found"),
            ).model_dump(exclude_none=True),
        )

    except Exception as err:
        logger.error(f"[MCP Data Plane] Execution error: {err}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=DataPlaneJSONRPCResponse(
                id=req_id, error=DataPlaneJSONRPCError(code=-32603, message=str(err))
            ).model_dump(exclude_none=True),
        )
