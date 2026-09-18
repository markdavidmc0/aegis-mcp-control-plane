"""Tool Stub Generator for Client-Side Code Mode Agents."""

from typing import Any

TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
}


def generate_python_stub(tool_name: str, description: str, input_schema: dict[str, Any]) -> str:
    """Generates an async Python function stub for Code Mode tool stubs."""
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    param_list = []
    for p_name, p_info in properties.items():
        p_type = TYPE_MAP.get(p_info.get("type", "Any"), "Any")
        default = "" if p_name in required else " = None"
        param_list.append(f"{p_name}: {p_type}{default}")

    params_str = ", ".join(param_list)
    return f'async def {tool_name}({params_str}) -> dict[str, Any]:\n    """{description}"""\n    pass'


def generate_catalog_stubs(tools: list[dict[str, Any]]) -> str:
    """Renders combined stubs for entire tool catalog."""
    stubs = []
    for tool in tools:
        name = tool.get("name")
        if name:
            schema = tool.get("inputSchema") or tool.get("parameters") or {}
            stubs.append(generate_python_stub(name, tool.get("description", ""), schema))
    return "\n\n".join(stubs)
