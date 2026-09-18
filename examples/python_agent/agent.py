"""Vortex Silicon AI Agent - Multi-Tool Roofline Analysis over MCP Gateway."""

import asyncio
from typing import Any

import httpx
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai_harness import CodeMode

CONTROL_PLANE_URL = "http://localhost:8000"
IDENTITY_HEADERS = {
    "X-User-ID": "usr_vortex_silicon_agent_01",
    "X-User-Role": "hardware_engineer",
    "X-User-Scopes": "tools:execute,llm:proxy",
}

# 1. Configure custom HTTP client attaching Envoy identity headers to all gateway traffic
gateway_client = httpx.AsyncClient(
    base_url=f"{CONTROL_PLANE_URL}/v1",
    headers=IDENTITY_HEADERS,
    timeout=60.0,
)

# 2. Point Pydantic AI model provider directly to our Control Plane AI Gateway
ai_gateway_model = OpenAIChatModel(
    "gpt-4o",
    provider=OpenAIProvider(
        base_url=f"{CONTROL_PLANE_URL}/v1",
        http_client=gateway_client,
        # api_key="your-api-key", # Add if required by your gateway
    ),
)

# 3. Initialize Agent with CodeMode harness enabled
silicon_agent = Agent(
    model=ai_gateway_model,
    system_prompt=(
        "You are an expert silicon performance engineer at Vortex Silicon Technologies. "
        "Use `discover_catalog_tools` to find available platform tools, then use "
        "`call_mcp_tool` and `execute_code_in_sandbox` to benchmark hardware limits "
        "and calculate Roofline bottleneck transitions."
    ),
    capabilities=[CodeMode(tools="all")],
)


@silicon_agent.tool
async def discover_catalog_tools(ctx: RunContext[None]) -> list[dict[str, Any]]:
    """Discovers available tools dynamically via MCP tool search (`tools/list`)."""
    async with httpx.AsyncClient(base_url=CONTROL_PLANE_URL, headers=IDENTITY_HEADERS) as client:
        payload = {"jsonrpc": "2.0", "id": "search-tools", "method": "tools/list"}
        res = await client.post("/api/v1/mcp", json=payload)
        res.raise_for_status()
        return res.json().get("result", {}).get("tools", [])


@silicon_agent.tool
async def call_mcp_tool(
    ctx: RunContext[None],
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Executes any registered catalog tool via the Control Plane MCP endpoint."""
    async with httpx.AsyncClient(base_url=CONTROL_PLANE_URL, headers=IDENTITY_HEADERS) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": f"call-{tool_name}",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        res = await client.post("/api/v1/mcp", json=payload)
        res.raise_for_status()
        return res.json().get("result", {})


@silicon_agent.tool
async def execute_code_in_sandbox(
    ctx: RunContext[None],
    code: str,
) -> dict[str, Any]:
    """Executes Python code snippets safely inside the sandboxed Data Plane REPL over MCP."""
    return await call_mcp_tool(ctx, tool_name="execute_code", arguments={"code": code})


async def main():
    """Run interactive demonstration of Vortex Silicon AI Agent."""
    prompt = (
        "1. Discover available tools using `discover_catalog_tools`.\n"
        "2. Fetch specs for 'vortex-npu-v2'.\n"
        "3. Benchmark float32 GEMM kernels across matrix dimensions [256, 1024, 2048].\n"
        "4. Calculate which dimensions operate above vs below the hardware ridge point."
    )

    print(f"[Vortex Agent] Starting Workflow via Control Plane Gateway...\nPrompt:\n{prompt}\n")

    try:
        result = await silicon_agent.run(prompt)
        print("\n[Vortex Agent] Roofline Optimization Report:\n")
        print(result.data)
    finally:
        await gateway_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
