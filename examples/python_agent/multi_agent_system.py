"""Vortex Silicon Multi-Agent System - Supervisor-Worker Architecture.

Demonstrates hierarchical multi-agent orchestration conforming to Aegis Control Plane:
- SiliconBenchmarkLead (SUPERVISOR): Orchestrates benchmarking workflows and delegates tasks.
- MontyKernelProfiler (WORKER): Executes sandboxed kernel profiling over Monty/MCP.
- RooflineAuditor (WORKER): Audits arithmetic intensity against accelerator specifications.
"""

import asyncio
from typing import Any

import httpx
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

CONTROL_PLANE_URL = "http://localhost:8000"

# 4-Tuple composite identity headers for the Lead Supervisor
LEAD_IDENTITY_HEADERS = {
    "X-Actor-ID": "usr_vortex_lead",
    "X-User-ID": "usr_vortex_lead",
    "X-Agent-ID": "SiliconBenchmarkLead",
    "X-Cost-Centre-ID": "silicon-perf-lab",
    "X-Session-ID": "sess-benchmark-flow-001",
    "X-User-Role": "hardware_engineer",
    "X-User-Scopes": "tools:execute,llm:proxy",
}

gateway_client = httpx.AsyncClient(
    base_url=f"{CONTROL_PLANE_URL}/v1",
    headers=LEAD_IDENTITY_HEADERS,
    timeout=60.0,
)

ai_gateway_model = OpenAIChatModel(
    "gpt-4o",
    provider=OpenAIProvider(
        base_url=f"{CONTROL_PLANE_URL}/v1",
        http_client=gateway_client,
    ),
)

# 1. Lead Supervisor Agent
lead_agent = Agent(
    model=ai_gateway_model,
    system_prompt=(
        "You are the SiliconBenchmarkLead supervisor at Vortex Silicon Technologies. "
        "You coordinate silicon benchmark evaluations by delegating tasks to MontyKernelProfiler, "
        "RooflineAuditor, and TSSafetyVerifier using the orchestrator handoff protocol."
    ),
)

# 2. Worker 1: MontyKernelProfiler
profiler_agent = Agent(
    model=ai_gateway_model,
    system_prompt=(
        "You are the MontyKernelProfiler worker at Vortex Silicon Technologies. "
        "You profile tensor compute kernels using sandboxed execution and hardware measurement tools."
    ),
)

# 3. Worker 2: RooflineAuditor
auditor_agent = Agent(
    model=ai_gateway_model,
    system_prompt=(
        "You are the RooflineAuditor worker at Vortex Silicon Technologies. "
        "You calculate arithmetic intensity, compare with accelerator hardware limits, "
        "and evaluate ridge points."
    ),
)


@lead_agent.tool
async def delegate_to_worker(
    ctx: RunContext[None],
    target_agent_id: str,
    task_instructions: str,
    context_data: dict[str, Any],
) -> dict[str, Any]:
    """Delegates a specialized subtask from SiliconBenchmarkLead to an authorized sub-agent."""
    async with httpx.AsyncClient(base_url=CONTROL_PLANE_URL, headers=LEAD_IDENTITY_HEADERS) as client:
        payload = {
            "parent_session_id": LEAD_IDENTITY_HEADERS["X-Session-ID"],
            "caller_agent_id": "SiliconBenchmarkLead",
            "target_agent_id": target_agent_id,
            "task_instructions": task_instructions,
            "context_data": context_data,
        }
        res = await client.post("/api/v1/orchestrator/handoff", json=payload)
        res.raise_for_status()
        return res.json()


@profiler_agent.tool
async def profile_kernel(
    ctx: RunContext[None],
    matrix_dim: int,
    data_type: str = "float32",
) -> dict[str, Any]:
    """Executes tensor kernel profiling for a given dimension and data type via MCP."""
    async with httpx.AsyncClient(base_url=CONTROL_PLANE_URL, headers=LEAD_IDENTITY_HEADERS) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "profile-tensor-kernel",
            "method": "tools/call",
            "params": {
                "name": "profile_tensor_kernel",
                "arguments": {"matrix_dim": matrix_dim, "data_type": data_type},
            },
        }
        res = await client.post("/api/v1/mcp", json=payload)
        res.raise_for_status()
        return res.json().get("result", {})


@auditor_agent.tool
async def audit_roofline(
    ctx: RunContext[None],
    architecture: str,
    gflops: float,
    bandwidth_gbps: float,
) -> dict[str, Any]:
    """Fetches accelerator specifications and calculates operational intensity relative to ridge point."""
    async with httpx.AsyncClient(base_url=CONTROL_PLANE_URL, headers=LEAD_IDENTITY_HEADERS) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "get-accelerator-specs",
            "method": "tools/call",
            "params": {
                "name": "get_accelerator_specs",
                "arguments": {"architecture": architecture},
            },
        }
        res = await client.post("/api/v1/mcp", json=payload)
        res.raise_for_status()
        specs = res.json().get("result", {})
        ridge_point = specs.get("ridge_point", 125.0)
        arithmetic_intensity = gflops / bandwidth_gbps if bandwidth_gbps > 0 else 0.0
        return {
            "specs": specs,
            "arithmetic_intensity": round(arithmetic_intensity, 2),
            "ridge_point": ridge_point,
            "is_compute_bound": arithmetic_intensity >= ridge_point,
        }


async def register_specs_with_control_plane(client: httpx.AsyncClient) -> None:
    """Registers the multi-agent system specifications in the Aegis orchestrator registry."""
    specs = [
        {
            "agent_id": "SiliconBenchmarkLead",
            "name": "Silicon Benchmark Lead",
            "description": "Supervisor managing hardware roofline benchmark workflows",
            "topology": "SUPERVISOR",
            "model": "gpt-4o",
            "system_prompt": "You coordinate silicon benchmark evaluations.",
            "allowed_tools": ["discover_catalog_tools"],
            "sub_agents": ["MontyKernelProfiler", "RooflineAuditor", "TSSafetyVerifier"],
            "max_steps": 15,
            "timeout_seconds": 120.0,
        },
        {
            "agent_id": "MontyKernelProfiler",
            "name": "Monty Kernel Profiler",
            "description": "Worker executing sandboxed kernel tensor operations",
            "topology": "WORKER",
            "model": "gpt-4o",
            "system_prompt": "You profile tensor compute kernels.",
            "allowed_tools": ["execute_code", "profile_tensor_kernel"],
            "sub_agents": [],
            "max_steps": 10,
            "timeout_seconds": 60.0,
        },
        {
            "agent_id": "RooflineAuditor",
            "name": "Roofline Auditor",
            "description": "Worker auditing operational intensity against hardware bounds",
            "topology": "WORKER",
            "model": "gpt-4o",
            "system_prompt": "You calculate arithmetic intensity and ridge points.",
            "allowed_tools": ["get_accelerator_specs"],
            "sub_agents": [],
            "max_steps": 10,
            "timeout_seconds": 60.0,
        },
        {
            "agent_id": "TSSafetyVerifier",
            "name": "TS Safety Verifier",
            "description": "TypeScript worker verifying type soundness and AST bounds",
            "topology": "WORKER",
            "model": "claude-3-5-sonnet",
            "system_prompt": "You verify type safety and memory limit bounds.",
            "allowed_tools": ["ast_scan"],
            "sub_agents": [],
            "max_steps": 8,
            "timeout_seconds": 45.0,
        },
    ]

    for spec in specs:
        res = await client.post(
            "/api/v1/orchestrator/specs",
            json=spec,
            headers={"X-User-ID": "eng_lead_01", "X-User-Role": "admin"},
        )
        res.raise_for_status()


async def main() -> None:
    """Run interactive demonstration of multi-agent supervisor-worker workflow."""
    print("[Lead Supervisor] Registering multi-agent topology with Control Plane...")
    async with httpx.AsyncClient(base_url=CONTROL_PLANE_URL) as client:
        await register_specs_with_control_plane(client)

    print("[Lead Supervisor] Initiating benchmark evaluation flow...")
    prompt = (
        "Coordinate a complete roofline evaluation on vortex-npu-v2: "
        "first delegate profiling to MontyKernelProfiler for matrix dimension 2048, "
        "then delegate roofline arithmetic intensity auditing to RooflineAuditor, "
        "and finally delegate cross-ecosystem AST safety verification to TSSafetyVerifier "
        "to verify AST memory constraints for matrix dimension 2048."
    )
    try:
        result = await lead_agent.run(prompt)
        print("\n[Lead Supervisor] Workflow Completed:")
        print(result.data)
    finally:
        await gateway_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
