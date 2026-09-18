"""Tool Catalog Registration Endpoint."""

import json
import logging
from typing import Any

import logfire
from fastapi import APIRouter, Depends, HTTPException, status

from src.config import resolve_tools_dir
from src.control_plane.dependencies import UserContext, get_user_context
from src.control_plane.schemas import (
    CatalogStubsResponse,
    ToolRegistrationSchema,
    ToolStubResponse,
)
from src.control_plane.stub_generator import (
    generate_catalog_stubs,
    generate_python_stub,
)

logger = logging.getLogger("mvcp.tool_registration")
router = APIRouter(prefix="/api/v1/tools", tags=["Tool Catalog"])


def load_catalog_tools() -> list[dict[str, Any]]:
    """Loads tools from catalog.json in the tools directory."""
    target_dir = resolve_tools_dir()
    catalog_path = target_dir / "catalog.json"
    if not catalog_path.exists():
        return []
    try:
        with open(catalog_path, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("tools", []) if isinstance(data, dict) else data
    except Exception as e:
        logger.warning(f"Could not parse catalog.json: {e}")
        return []


@router.get("/stubs", response_model=CatalogStubsResponse, status_code=status.HTTP_200_OK)
async def get_all_tool_stubs(
    user: UserContext = Depends(get_user_context),
) -> CatalogStubsResponse:
    """Returns generated Python function stubs for all tools in the catalog."""
    with logfire.span("tool_stubs.get_all", user_id=user.user_id):
        tools = load_catalog_tools()
        stubs_text = generate_catalog_stubs(tools)
        tool_names = [t["name"] for t in tools if isinstance(t, dict) and t.get("name")]
        return CatalogStubsResponse(stubs=stubs_text, tools=tool_names)


@router.get("/stubs/{tool_name}", response_model=ToolStubResponse, status_code=status.HTTP_200_OK)
async def get_tool_stub(
    tool_name: str,
    user: UserContext = Depends(get_user_context),
) -> ToolStubResponse:
    """Returns generated Python function stub for a single specified tool."""
    with logfire.span("tool_stubs.get_single", user_id=user.user_id, tool_name=tool_name):
        tools = load_catalog_tools()
        target_tool = next((t for t in tools if isinstance(t, dict) and t.get("name") == tool_name), None)
        if not target_tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found in catalog.",
            )
        schema = target_tool.get("inputSchema") or target_tool.get("parameters") or {}
        description = target_tool.get("description", "")
        stub_code = generate_python_stub(tool_name, description, schema)
        return ToolStubResponse(tool_name=tool_name, stub=stub_code)


@router.post("/register", status_code=status.HTTP_200_OK)
async def register_tool(
    payload: ToolRegistrationSchema,
    user: UserContext = Depends(get_user_context),
) -> dict[str, Any]:
    """Atomic tool catalog update (catalog.json)."""
    target_dir = resolve_tools_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    catalog_path = target_dir / "catalog.json"
    temp_path = target_dir / ".catalog.json.tmp"

    tools_list: list[dict[str, Any]] = []

    if catalog_path.exists():
        try:
            with open(catalog_path, encoding="utf-8") as f:
                data = json.load(f)
                tools_list = data.get("tools", []) if isinstance(data, dict) else data
        except Exception as e:
            logger.warning(
                f"Could not parse existing catalog.json: {e}. Initializing fresh list."
            )

    new_item = {
        "name": payload.name,
        "description": payload.description,
        "parameters": payload.parameters,
        "inputSchema": payload.parameters,
    }
    if payload.entrypoint:
        new_item["entrypoint"] = payload.entrypoint

    # Atomic write-replace
    updated_tools = [t for t in tools_list if t.get("name") != payload.name]
    updated_tools.append(new_item)

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump({"tools": updated_tools}, f, indent=2)
        temp_path.replace(catalog_path)

        return {
            "status": "registered",
            "tool": new_item,
            "catalog_path": str(catalog_path),
        }
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write tool catalog: {e}",
        )
