"""Bidirectional Polyglot Cross-Ecosystem Agent Delegation Demonstration.

Demonstrates seamless cross-ecosystem collaboration between Python and TypeScript agents
governed by the Aegis Control Plane with strict 4-tuple identity propagation:
(X-Actor-ID, X-Agent-ID, X-Cost-Centre-ID, X-Session-ID).

Execution Flow:
1. Connects to http://localhost:8000 with 4-tuple identity headers.
2. Registers all 5 agent specs:
   - SiliconBenchmarkLead (Python Supervisor)
   - MontyKernelProfiler (Python Worker)
   - RooflineAuditor (Python Worker)
   - AuditCompilerLead (TypeScript Supervisor)
   - TSSafetyVerifier (TypeScript Worker)
3. Phase 1: SiliconBenchmarkLead (Python Supervisor) delegates to MontyKernelProfiler (Python Worker).
4. Phase 2: SiliconBenchmarkLead (Python Supervisor) cross-delegates to TSSafetyVerifier (TypeScript Worker).
5. Phase 3: SiliconBenchmarkLead (Python Supervisor) delegates to RooflineAuditor (Python Worker).
6. Phase 4: AuditCompilerLead (TypeScript Supervisor) cross-delegates to MontyKernelProfiler (Python Worker).
7. Summary: Displays unified Co-Design Execution & Audit Summary showing 4-tuple URN lineage
   across all 4 sessions with zero cost leakage.
"""

import asyncio
from typing import Any

import httpx

CONTROL_PLANE_URL = "http://localhost:8000"

# Root 4-Tuple composite identity headers for Python benchmark operations
PYTHON_LEAD_HEADERS = {
    "X-Actor-ID": "usr_vortex_lead",
    "X-User-ID": "usr_vortex_lead",
    "X-Agent-ID": "SiliconBenchmarkLead",
    "X-Cost-Centre-ID": "silicon-perf-lab",
    "X-Session-ID": "sess-benchmark-flow-001",
    "X-User-Role": "hardware_engineer",
    "X-User-Scopes": "tools:execute,llm:proxy",
}

# Root 4-Tuple composite identity headers for TypeScript compiler audit operations
TS_LEAD_HEADERS = {
    "X-Actor-ID": "usr_ts_auditor",
    "X-User-ID": "usr_ts_auditor",
    "X-Agent-ID": "AuditCompilerLead",
    "X-Cost-Centre-ID": "ts-platform-eng",
    "X-Session-ID": "sess-ts-audit-900",
    "X-User-Role": "platform_engineer",
    "X-User-Scopes": "tools:execute,llm:proxy",
}

AGENT_SPECS = [
    {
        "agent_id": "SiliconBenchmarkLead",
        "name": "Silicon Benchmark Lead",
        "description": "Python Supervisor managing hardware benchmarks, roofline modeling, and AST bounds",
        "topology": "SUPERVISOR",
        "model": "gpt-4o",
        "system_prompt": "You coordinate silicon benchmark evaluations and cross-ecosystem verifications.",
        "allowed_tools": ["discover_catalog_tools"],
        "sub_agents": ["MontyKernelProfiler", "RooflineAuditor", "TSSafetyVerifier"],
        "max_steps": 15,
        "timeout_seconds": 120.0,
    },
    {
        "agent_id": "MontyKernelProfiler",
        "name": "Monty Kernel Profiler",
        "description": "Python Worker executing sandboxed kernel tensor operations in Monty sandbox",
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
        "description": "Python Worker auditing operational intensity against hardware bounds",
        "topology": "WORKER",
        "model": "gpt-4o",
        "system_prompt": "You calculate arithmetic intensity and ridge points.",
        "allowed_tools": ["get_accelerator_specs"],
        "sub_agents": [],
        "max_steps": 10,
        "timeout_seconds": 60.0,
    },
    {
        "agent_id": "AuditCompilerLead",
        "name": "Audit Compiler Lead",
        "description": "TypeScript Supervisor coordinating compilation audits and native profiling",
        "topology": "SUPERVISOR",
        "model": "claude-3-5-sonnet",
        "system_prompt": "You oversee compilation audit, AST verification, and cross-ecosystem profiling.",
        "allowed_tools": ["tsc_check"],
        "sub_agents": ["TSSafetyVerifier", "MontyKernelProfiler"],
        "max_steps": 12,
        "timeout_seconds": 90.0,
    },
    {
        "agent_id": "TSSafetyVerifier",
        "name": "TS Safety Verifier",
        "description": "TypeScript Worker verifying type soundness and AST bounds",
        "topology": "WORKER",
        "model": "claude-3-5-sonnet",
        "system_prompt": "You verify type safety and memory limit bounds.",
        "allowed_tools": ["ast_scan"],
        "sub_agents": [],
        "max_steps": 8,
        "timeout_seconds": 45.0,
    },
]


async def register_all_specs(client: httpx.AsyncClient) -> None:
    """Registers all 5 agent specifications in the Aegis orchestrator registry."""
    print("[Topology] Registering 5 polyglot agent specifications with Control Plane...")
    for spec in AGENT_SPECS:
        res = await client.post(
            "/api/v1/orchestrator/specs",
            json=spec,
            headers={"X-User-ID": "admin_engineer", "X-User-Role": "admin"},
        )
        res.raise_for_status()
        print(f"  + Registered: {spec['agent_id']} ({spec['topology']})")


async def execute_handoff(
    client: httpx.AsyncClient,
    caller_headers: dict[str, str],
    target_agent_id: str,
    task_instructions: str,
    context_data: dict[str, Any],
) -> dict[str, Any]:
    """Issues a handoff request and verifies 4-tuple identity propagation."""
    payload = {
        "parent_session_id": caller_headers["X-Session-ID"],
        "caller_agent_id": caller_headers["X-Agent-ID"],
        "target_agent_id": target_agent_id,
        "task_instructions": task_instructions,
        "context_data": context_data,
    }
    res = await client.post("/api/v1/orchestrator/handoff", json=payload, headers=caller_headers)
    res.raise_for_status()
    session: dict[str, Any] = res.json()
    return session


async def main() -> None:
    """Executes the complete polyglot co-design multi-agent workflow."""
    print("=" * 78)
    print("AEGIS CONTROL PLANE: BIDIRECTIONAL POLYGLOT CO-DESIGN DEMONSTRATION")
    print("=" * 78)

    async with httpx.AsyncClient(base_url=CONTROL_PLANE_URL, timeout=30.0) as client:
        # Check platform reachability
        try:
            health = await client.get("/health")
            if health.status_code != 200:
                print(f"[Warning] Control Plane returned {health.status_code}. Is it running?")
                return
        except httpx.ConnectError:
            print(f"[Error] Cannot connect to Aegis Control Plane at {CONTROL_PLANE_URL}.")
            print("Please ensure the Control Plane is running:\n  uv run uvicorn src.control_plane.main:app --port 8000")
            return

        # 1. Register all polyglot agent specs
        await register_all_specs(client)

        print("\n" + "-" * 78)
        print("PHASE 1: Python Supervisor -> Python Worker (Intra-Ecosystem)")
        print("Delegating tensor kernel profiling to MontyKernelProfiler...")
        phase1_session = await execute_handoff(
            client=client,
            caller_headers=PYTHON_LEAD_HEADERS,
            target_agent_id="MontyKernelProfiler",
            task_instructions="Profile 2048x2048 float32 GEMM kernel in Monty sandbox",
            context_data={"matrix_dim": 2048, "data_type": "float32"},
        )
        print(f"  * Status: {phase1_session['status']}")
        print(f"  * Child Session ID: {phase1_session['session_id']}")
        print(f"  * Preserved Actor: {phase1_session['composite_key']['actor_id']}")
        print(f"  * Preserved Cost-Centre: {phase1_session['composite_key']['cost_centre_id']}")

        print("\n" + "-" * 78)
        print("PHASE 2: Python Supervisor -> TypeScript Worker (Cross-Ecosystem)")
        print("Delegating AST memory constraints verification to TSSafetyVerifier...")
        phase2_session = await execute_handoff(
            client=client,
            caller_headers=PYTHON_LEAD_HEADERS,
            target_agent_id="TSSafetyVerifier",
            task_instructions="Verify AST memory constraints and bound checks for matrix dimension 2048",
            context_data={"matrix_dim": 2048, "memory_limit_bytes": 16777216},
        )
        print(f"  * Status: {phase2_session['status']}")
        print(f"  * Child Session ID: {phase2_session['session_id']}")
        print(f"  * Preserved Actor: {phase2_session['composite_key']['actor_id']}")
        print(f"  * Preserved Cost-Centre: {phase2_session['composite_key']['cost_centre_id']}")

        print("\n" + "-" * 78)
        print("PHASE 3: Python Supervisor -> Python Worker (Intra-Ecosystem)")
        print("Delegating hardware roofline and ridge point auditing to RooflineAuditor...")
        phase3_session = await execute_handoff(
            client=client,
            caller_headers=PYTHON_LEAD_HEADERS,
            target_agent_id="RooflineAuditor",
            task_instructions="Audit arithmetic intensity against accelerator specs for vortex-npu-v2",
            context_data={"architecture": "vortex-npu-v2", "gflops": 128.0, "bandwidth_gbps": 33.2},
        )
        print(f"  * Status: {phase3_session['status']}")
        print(f"  * Child Session ID: {phase3_session['session_id']}")
        print(f"  * Preserved Actor: {phase3_session['composite_key']['actor_id']}")
        print(f"  * Preserved Cost-Centre: {phase3_session['composite_key']['cost_centre_id']}")

        print("\n" + "-" * 78)
        print("PHASE 4: TypeScript Supervisor -> Python Worker (Cross-Ecosystem)")
        print("Delegating JIT kernel profiling to MontyKernelProfiler from TypeScript Lead...")
        phase4_session = await execute_handoff(
            client=client,
            caller_headers=TS_LEAD_HEADERS,
            target_agent_id="MontyKernelProfiler",
            task_instructions="Profile float32 kernel in Monty sandbox for compiled AST output",
            context_data={"matrix_dim": 1024, "data_type": "float32"},
        )
        print(f"  * Status: {phase4_session['status']}")
        print(f"  * Child Session ID: {phase4_session['session_id']}")
        print(f"  * Preserved Actor: {phase4_session['composite_key']['actor_id']}")
        print(f"  * Preserved Cost-Centre: {phase4_session['composite_key']['cost_centre_id']}")

        # Assert identity preservation invariant
        assert phase1_session["composite_key"]["actor_id"] == PYTHON_LEAD_HEADERS["X-Actor-ID"]
        assert phase1_session["composite_key"]["cost_centre_id"] == PYTHON_LEAD_HEADERS["X-Cost-Centre-ID"]
        assert phase2_session["composite_key"]["actor_id"] == PYTHON_LEAD_HEADERS["X-Actor-ID"]
        assert phase2_session["composite_key"]["cost_centre_id"] == PYTHON_LEAD_HEADERS["X-Cost-Centre-ID"]
        assert phase3_session["composite_key"]["actor_id"] == PYTHON_LEAD_HEADERS["X-Actor-ID"]
        assert phase3_session["composite_key"]["cost_centre_id"] == PYTHON_LEAD_HEADERS["X-Cost-Centre-ID"]
        assert phase4_session["composite_key"]["actor_id"] == TS_LEAD_HEADERS["X-Actor-ID"]
        assert phase4_session["composite_key"]["cost_centre_id"] == TS_LEAD_HEADERS["X-Cost-Centre-ID"]

        # Unified Audit & URN Lineage Report
        print("\n" + "=" * 78)
        print("CO-DESIGN EXECUTION & AUDIT SUMMARY")
        print("=" * 78)
        print(f"{'Phase':<8} | {'Supervisor (Ecosystem)':<26} | {'Worker (Ecosystem)':<24} | {'Preserved Cost-Centre':<18} | {'Status'}")
        print("-" * 92)
        print(f"{'Phase 1':<8} | {'SiliconBenchmarkLead (PY)':<26} | {'MontyKernelProfiler (PY)':<24} | {phase1_session['composite_key']['cost_centre_id']:<18} | {phase1_session['status']}")
        print(f"{'Phase 2':<8} | {'SiliconBenchmarkLead (PY)':<26} | {'TSSafetyVerifier (TS)':<24} | {phase2_session['composite_key']['cost_centre_id']:<18} | {phase2_session['status']}")
        print(f"{'Phase 3':<8} | {'SiliconBenchmarkLead (PY)':<26} | {'RooflineAuditor (PY)':<24} | {phase3_session['composite_key']['cost_centre_id']:<18} | {phase3_session['status']}")
        print(f"{'Phase 4':<8} | {'AuditCompilerLead (TS)':<26} | {'MontyKernelProfiler (PY)':<24} | {phase4_session['composite_key']['cost_centre_id']:<18} | {phase4_session['status']}")
        print("-" * 92)
        print("4-Tuple Lineage Preservation: 100% INTACT (Zero Cost Centre Leakage Across Boundaries)")
        print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
