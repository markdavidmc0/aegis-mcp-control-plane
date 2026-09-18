"""Unit Tests for Data Plane Pydantic Schemas and AST Architecture Isolation."""

import ast
from pathlib import Path

import pytest

from src.data_plane.schemas import (
    DataPlaneJSONRPCError,
    DataPlaneJSONRPCRequest,
    DataPlaneJSONRPCResponse,
    DataPlaneUserContext,
)

# Resolve repo root relative to file location
CURRENT_FILE = Path(__file__).resolve()
REPO_ROOT = next((p for p in CURRENT_FILE.parents if (p / "src").exists()), CURRENT_FILE.parents[2])
SCHEMAS_FILE = REPO_ROOT / "src" / "data_plane" / "schemas.py"


@pytest.mark.unit
def test_data_plane_user_context_defaults():
    """Verify DataPlaneUserContext initializes with correct defaults."""
    ctx = DataPlaneUserContext(user_id="usr_test_123")
    assert ctx.user_id == "usr_test_123"
    assert ctx.role == "user"
    assert ctx.scopes == []


@pytest.mark.unit
def test_data_plane_jsonrpc_request_serialization():
    """Verify DataPlaneJSONRPCRequest serializes to spec-compliant JSON-RPC 2.0 object."""
    req = DataPlaneJSONRPCRequest(
        id=1,
        method="tools/call",
        params={"name": "execute_code", "arguments": {"code": "print(1)"}},
    )
    dump = req.model_dump()
    assert dump["jsonrpc"] == "2.0"
    assert dump["id"] == 1
    assert dump["method"] == "tools/call"


@pytest.mark.unit
def test_data_plane_jsonrpc_response_success():
    """Verify DataPlaneJSONRPCResponse formats successful JSON-RPC payload."""
    resp = DataPlaneJSONRPCResponse(
        id="req-123",
        result={"status": "SUCCESS", "execution_time_ms": 12.5},
    )
    dump = resp.model_dump(exclude_none=True)
    assert dump["jsonrpc"] == "2.0"
    assert dump["id"] == "req-123"
    assert dump["result"]["status"] == "SUCCESS"
    assert "error" not in dump


@pytest.mark.unit
def test_data_plane_jsonrpc_response_error():
    """Verify DataPlaneJSONRPCResponse formats error JSON-RPC payload."""
    err = DataPlaneJSONRPCError(code=-32601, message="Method not found")
    resp = DataPlaneJSONRPCResponse(id=42, error=err)
    dump = resp.model_dump(exclude_none=True)
    assert dump["jsonrpc"] == "2.0"
    assert dump["id"] == 42
    assert dump["error"]["code"] == -32601
    assert dump["error"]["message"] == "Method not found"


@pytest.mark.unit
def test_schemas_ast_boundary_isolation():
    """AST boundary test verifying src/data_plane/schemas.py has ZERO imports from control_plane."""
    tree = ast.parse(SCHEMAS_FILE.read_text(encoding="utf-8"), filename=str(SCHEMAS_FILE))
    forbidden = ("src.control_plane", "control_plane")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), f"Forbidden import '{alias.name}' in schemas.py"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden), f"Forbidden import from '{module}' in schemas.py"
