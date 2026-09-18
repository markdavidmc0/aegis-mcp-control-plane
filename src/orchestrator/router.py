"""FastAPI router for agent orchestration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from src.control_plane.dependencies import get_user_context
from src.control_plane.schemas import AgentCompositeKey, UserContext
from src.orchestrator.registry import AgentRegistry, default_registry
from src.orchestrator.runtime import AgentRuntimeOrchestrator, default_orchestrator
from src.orchestrator.schemas import (
    AgentHandoffRequest,
    AgentRunRequest,
    AgentSessionState,
    AgentSpec,
)

router = APIRouter(prefix="/api/v1/orchestrator", tags=["orchestrator"])


def get_registry() -> AgentRegistry:
    """Dependency provider for AgentRegistry."""
    return default_registry


def get_orchestrator(
    registry: Annotated[AgentRegistry, Depends(get_registry)],
) -> AgentRuntimeOrchestrator:
    """Dependency provider for AgentRuntimeOrchestrator."""
    if registry is default_registry:
        return default_orchestrator
    return AgentRuntimeOrchestrator(registry=registry)


@router.post("/specs", response_model=AgentSpec, status_code=status.HTTP_201_CREATED)
async def register_agent_spec(
    spec: AgentSpec,
    registry: Annotated[AgentRegistry, Depends(get_registry)],
    user: Annotated[UserContext, Depends(get_user_context)],
) -> AgentSpec:
    """Register a new agent specification in the manifest registry."""
    registry.register(spec)
    return spec


@router.get("/specs", response_model=list[AgentSpec])
async def list_agent_specs(
    registry: Annotated[AgentRegistry, Depends(get_registry)],
    user: Annotated[UserContext, Depends(get_user_context)],
) -> list[AgentSpec]:
    """List all registered agent specifications."""
    return registry.list()


@router.get("/specs/{agent_id}", response_model=AgentSpec)
async def get_agent_spec(
    agent_id: str,
    registry: Annotated[AgentRegistry, Depends(get_registry)],
    user: Annotated[UserContext, Depends(get_user_context)],
) -> AgentSpec:
    """Retrieve an agent specification by agent_id."""
    spec = registry.get(agent_id)
    if not spec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found.",
        )
    return spec


@router.post("/runs/{agent_id}", response_model=AgentSessionState, status_code=status.HTTP_200_OK)
async def run_agent(
    agent_id: str,
    request: AgentRunRequest,
    orchestrator: Annotated[AgentRuntimeOrchestrator, Depends(get_orchestrator)],
    user: Annotated[UserContext, Depends(get_user_context)],
) -> AgentSessionState:
    """Initiate an agent run using caller composite key identity."""
    spec = orchestrator.registry.get(agent_id)
    if not spec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found.",
        )

    # Derive composite key for the run
    caller_key = user.composite_key
    if caller_key:
        actor_id = caller_key.actor_id
        cost_centre_id = caller_key.cost_centre_id
        session_id = caller_key.session_id
    else:
        actor_id = user.user_id
        cost_centre_id = "default-cost-centre"
        session_id = "default-session"

    key = AgentCompositeKey(
        actor_id=actor_id,
        agent_id=agent_id,
        cost_centre_id=cost_centre_id,
        session_id=session_id,
    )

    try:
        return await orchestrator.run(key=key, request=request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/handoff", response_model=AgentSessionState, status_code=status.HTTP_200_OK)
async def handoff_agent(
    request: AgentHandoffRequest,
    orchestrator: Annotated[AgentRuntimeOrchestrator, Depends(get_orchestrator)],
    user: Annotated[UserContext, Depends(get_user_context)],
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-ID")] = None,
    x_cost_centre_id: Annotated[str | None, Header(alias="X-Cost-Centre-ID")] = None,
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
) -> AgentSessionState:
    """Delegate a subtask from a supervisor agent to an authorized worker agent."""
    supervisor = orchestrator.registry.get(request.caller_agent_id)
    if not supervisor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supervisor agent '{request.caller_agent_id}' is not registered.",
        )

    # Derive composite key for the parent/caller from header fallbacks or user.composite_key
    actor_id = (
        (x_actor_id.strip() if x_actor_id and x_actor_id.strip() else None)
        or (user.composite_key.actor_id if user.composite_key else None)
        or user.user_id
    )
    cost_centre_id = (
        (x_cost_centre_id.strip() if x_cost_centre_id and x_cost_centre_id.strip() else None)
        or (user.composite_key.cost_centre_id if user.composite_key else None)
        or "default-cost-centre"
    )
    session_id = (
        request.parent_session_id
        or (x_session_id.strip() if x_session_id and x_session_id.strip() else None)
        or (user.composite_key.session_id if user.composite_key else None)
        or "default-session"
    )

    parent_key = AgentCompositeKey(
        actor_id=actor_id,
        agent_id=request.caller_agent_id,
        cost_centre_id=cost_centre_id,
        session_id=session_id,
    )

    try:
        return await orchestrator.handoff(parent_key=parent_key, handoff=request)
    except ValueError as exc:
        msg = str(exc)
        if "is not registered" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/sessions/{session_id}", response_model=AgentSessionState)
async def get_session(
    session_id: str,
    orchestrator: Annotated[AgentRuntimeOrchestrator, Depends(get_orchestrator)],
    user: Annotated[UserContext, Depends(get_user_context)],
) -> AgentSessionState:
    """Retrieve session state by session_id."""
    session = orchestrator.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return session


@router.post("/sessions/{session_id}/cancel", response_model=AgentSessionState)
async def cancel_session(
    session_id: str,
    orchestrator: Annotated[AgentRuntimeOrchestrator, Depends(get_orchestrator)],
    user: Annotated[UserContext, Depends(get_user_context)],
) -> AgentSessionState:
    """Cancel an active or pending agent session."""
    session = orchestrator.cancel_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return session
