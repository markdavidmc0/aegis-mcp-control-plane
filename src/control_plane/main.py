"""Control Plane Entry Point."""

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.control_plane.llm_proxy import router as llm_proxy_router
from src.control_plane.mcp_router import router as mcp_router
from src.control_plane.schemas import ControlPlaneHealthResponse
from src.control_plane.tool_registration import router as tool_registration_router
from src.orchestrator.router import router as orchestrator_router

app = FastAPI(
    title="Arm AI Control Plane",
    description="Stateless Identity, MCP Gateway & Execution Routing Infrastructure",
    version="1.0.0",
)

# Pydantic Logfire Instrumentation
logfire.configure(
    service_name="aegis-control-plane",
    inspect_arguments=False,
)
logfire.instrument_fastapi(app)
logfire.instrument_pydantic()
logfire.instrument_httpx()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active Routers
app.include_router(llm_proxy_router)
app.include_router(mcp_router)
app.include_router(tool_registration_router)
app.include_router(orchestrator_router)


@app.get("/health", response_model=ControlPlaneHealthResponse)
@app.get("/api/v1/health", response_model=ControlPlaneHealthResponse)
async def health_check() -> ControlPlaneHealthResponse:
    """Return health readiness status and active identity layer."""
    return ControlPlaneHealthResponse(status="healthy", identity_layer="keycloak_wif")

