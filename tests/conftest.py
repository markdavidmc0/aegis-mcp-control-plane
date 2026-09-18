"""Global Pytest Fixtures and Service Overrides."""

import os
from collections.abc import Generator

# Ensure test execution does not export telemetry to remote Logfire project
os.environ["LOGFIRE_SEND_TO_LOGFIRE"] = "false"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.config import get_settings
from src.control_plane.dependencies import get_data_plane_client, get_user_context
from src.control_plane.main import app as control_plane_app
from src.control_plane.schemas import UserContext
from src.data_plane.mcp_server import app as data_plane_app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clears Pydantic settings cache before and after each test execution."""
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()
    yield
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()


@pytest.fixture(autouse=True)
def set_unit_test_env(monkeypatch: pytest.MonkeyPatch):
    """Sets standard default environment variables across unit tests."""
    monkeypatch.setenv("GCP_PROJECT_ID", "test-gcp-project")
    monkeypatch.setenv("GCP_LOCATION", "us-central1")
    monkeypatch.setenv("LOGFIRE_SEND_TO_LOGFIRE", "false")


@pytest.fixture(autouse=True)
def mock_auth_bypass(request: pytest.FixtureRequest, app: FastAPI):
    """Bypasses authentication automatically for Control Plane endpoint tests.

    To test auth failure cases (e.g. 401 Unauthorized), decorate the test function with:
    `@pytest.mark.unauthenticated`
    """
    if request.node.get_closest_marker("unauthenticated") is not None or "unauthenticated" in request.keywords:
        app.dependency_overrides.pop(get_user_context, None)
        yield
        app.dependency_overrides.pop(get_user_context, None)
        return

    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="unit-test-user-001",
        role="admin",
        scopes=["llm:proxy", "tools:register", "tools:execute"],
    )
    yield
    app.dependency_overrides.pop(get_user_context, None)


@pytest.fixture
def app() -> FastAPI:
    """Provides Control Plane FastAPI app instance."""
    return control_plane_app


@pytest.fixture
def test_client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Provides TestClient with managed lifespan context."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def mock_data_plane_client_override():
    """Proxies Control Plane HTTP calls to Data Plane FastAPI app in-memory."""

    async def _get_in_memory_data_plane_client():
        async with AsyncClient(
            transport=ASGITransport(app=data_plane_app),
            base_url="http://data-plane:8001",
        ) as client:
            yield client

    control_plane_app.dependency_overrides[get_data_plane_client] = _get_in_memory_data_plane_client
    yield
    control_plane_app.dependency_overrides.pop(get_data_plane_client, None)
