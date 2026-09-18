"""Integration and Unit Tests for Control Plane Endpoints & Stub Generator."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.control_plane.main import app
from src.control_plane.stub_generator import generate_catalog_stubs, generate_python_stub

client = TestClient(app)


@pytest.mark.unit
def test_health_check_endpoint():
    """Verify Control Plane /health returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.unit
def test_tool_registration_endpoint_atomic_upsert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifies POST /api/v1/tools/register atomic catalog.json creation and update."""
    target_dir = tmp_path / "custom_tools_dir"
    monkeypatch.setenv("ARM_TOOLS_DIR", str(target_dir))

    payload = {
        "name": "vector_accelerator",
        "description": "Arm SME2 vector kernel",
        "parameters": {"type": "object", "properties": {"len": {"type": "integer"}}},
        "entrypoint": "bin/vector_accel",
    }

    response = client.post("/api/v1/tools/register", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "registered"
    assert res_data["tool"]["name"] == "vector_accelerator"

    catalog_path = target_dir / "catalog.json"
    assert catalog_path.exists()

    with open(catalog_path, encoding="utf-8") as f:
        catalog_json = json.load(f)

    assert len(catalog_json["tools"]) == 1
    assert catalog_json["tools"][0]["name"] == "vector_accelerator"


@pytest.mark.unit
def test_stub_generator_single_tool():
    """Verify generate_python_stub builds correct async function signature."""
    stub = generate_python_stub(
        tool_name="compile_kernel",
        description="Compiles Arm C/C++ kernel source.",
        input_schema={
            "properties": {
                "source": {"type": "string"},
                "opt_level": {"type": "integer"},
            },
            "required": ["source"],
        },
    )

    assert "async def compile_kernel(source: str, opt_level: int = None)" in stub
    assert '"""Compiles Arm C/C++ kernel source."""' in stub


@pytest.mark.unit
def test_stub_generator_catalog():
    """Verify generate_catalog_stubs renders combined stub string."""
    catalog = [
        {"name": "tool_a", "description": "Tool A", "parameters": {"properties": {"a": {"type": "string"}}}},
        {"name": "tool_b", "description": "Tool B", "parameters": {"properties": {"b": {"type": "integer"}}}},
    ]

    stubs = generate_catalog_stubs(catalog)
    assert "async def tool_a(a: str = None)" in stubs
    assert "async def tool_b(b: int = None)" in stubs


@pytest.mark.unit
def test_get_tool_stubs_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify GET /api/v1/tools/stubs returns Python stubs for catalog tools."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ARM_TOOLS_DIR", str(tools_dir))

    catalog = {
        "tools": [
            {
                "name": "calc_tool",
                "description": "Performs fast calculation",
                "parameters": {
                    "type": "object",
                    "properties": {"val": {"type": "integer"}},
                    "required": ["val"],
                },
            }
        ]
    }
    (tools_dir / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")

    response = client.get("/api/v1/tools/stubs", headers={"X-User-ID": "test_user"})
    assert response.status_code == 200
    data = response.json()
    assert "calc_tool" in data["tools"]
    assert "async def calc_tool(val: int)" in data["stubs"]


@pytest.mark.unit
def test_get_single_tool_stub_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify GET /api/v1/tools/stubs/{tool_name} returns stub for matching tool."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ARM_TOOLS_DIR", str(tools_dir))

    catalog = {
        "tools": [
            {
                "name": "gemm_tool",
                "description": "Matrix GEMM accelerator",
                "parameters": {
                    "type": "object",
                    "properties": {"n": {"type": "integer"}},
                    "required": ["n"],
                },
            }
        ]
    }
    (tools_dir / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")

    # Success case
    resp = client.get("/api/v1/tools/stubs/gemm_tool", headers={"X-User-ID": "test_user"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_name"] == "gemm_tool"
    assert "async def gemm_tool(n: int)" in data["stub"]

    # 404 case
    resp_404 = client.get("/api/v1/tools/stubs/non_existent", headers={"X-User-ID": "test_user"})
    assert resp_404.status_code == 404

