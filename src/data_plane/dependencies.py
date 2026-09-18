"""FastAPI Application Lifespan and Dependency Providers."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from src.data_plane.context import get_current_user_context
from src.data_plane.schemas import DataPlaneUserContext
from src.data_plane.worker import DataPlaneSandboxRunner, LocalToolDispatcher


@asynccontextmanager
async def data_plane_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initializes execution state on application startup."""
    sandbox_runner = DataPlaneSandboxRunner()
    app.state.sandbox_runner = sandbox_runner
    app.state.dispatcher = LocalToolDispatcher(sandbox_runner=sandbox_runner)
    yield


def get_tool_dispatcher(request: Request) -> LocalToolDispatcher:
    """Retrieves the global LocalToolDispatcher instance."""
    if hasattr(request.app.state, "dispatcher"):
        return request.app.state.dispatcher
    return LocalToolDispatcher()


def get_sandbox_runner(request: Request) -> DataPlaneSandboxRunner:
    """Retrieves the global DataPlaneSandboxRunner instance."""
    if hasattr(request.app.state, "sandbox_runner"):
        return request.app.state.sandbox_runner
    return DataPlaneSandboxRunner()


def get_user_context() -> DataPlaneUserContext | None:
    """Retrieves task-isolated identity context."""
    return get_current_user_context()
