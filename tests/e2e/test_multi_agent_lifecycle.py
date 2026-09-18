"""End-to-End Multi-Agent Platform Lifecycle Test Suite.

Validates hybrid multi-agent execution lifecycle across:
- Registration of Python (SiliconBenchmarkLead -> MontyKernelProfiler, RooflineAuditor)
  and TypeScript (AuditCompilerLead -> TSSafetyVerifier) topologies.
- Invocation and execution of supervisor agents with 4-tuple key propagation:
  (X-Actor-ID, X-Agent-ID, X-Cost-Centre-ID, X-Session-ID).
- Multi-agent handoff delegation (Supervisor -> Worker) enforcing authorization boundaries.
- Mock MCP tool execution / sandboxed code execution in worker steps.
- Retrieval of full execution history, trace artifacts, and graceful teardown/cancellation.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.control_plane.main import app as control_plane_app
from src.orchestrator.registry import AgentRegistry
from src.orchestrator.router import get_orchestrator, get_registry
from src.orchestrator.runtime import AgentRuntimeOrchestrator
from src.orchestrator.schemas import AgentExecutionStatus


@pytest.fixture
def clean_e2e_registry():
    """Provides isolated registry and orchestrator for E2E multi-agent platform tests."""
    reg = AgentRegistry()
    orch = AgentRuntimeOrchestrator(registry=reg)

    control_plane_app.dependency_overrides[get_registry] = lambda: reg
    control_plane_app.dependency_overrides[get_orchestrator] = lambda: orch
    yield reg, orch
    control_plane_app.dependency_overrides.pop(get_registry, None)
    control_plane_app.dependency_overrides.pop(get_orchestrator, None)


@pytest.mark.e2e
@pytest.mark.unauthenticated
@pytest.mark.asyncio
async def test_multi_agent_system_registration_and_discovery(clean_e2e_registry):
    """Verify registration and discovery of Python and TypeScript multi-agent topologies."""
    async with AsyncClient(
        transport=ASGITransport(app=control_plane_app),
        base_url="http://testserver",
    ) as client:
        # 1. Register Python Topology: SiliconBenchmarkLead (SUPERVISOR) and workers
        python_supervisor = {
            "agent_id": "SiliconBenchmarkLead",
            "name": "Silicon Benchmark Lead",
            "description": "Supervisor managing hardware roofline benchmark workflows",
            "topology": "SUPERVISOR",
            "model": "gpt-4o",
            "system_prompt": "You coordinate silicon benchmark evaluations.",
            "allowed_tools": ["discover_catalog_tools"],
            "sub_agents": ["MontyKernelProfiler", "RooflineAuditor"],
            "max_steps": 15,
            "timeout_seconds": 120.0,
        }
        res = await client.post(
            "/api/v1/orchestrator/specs",
            json=python_supervisor,
            headers={"X-User-ID": "eng_lead_01", "X-User-Role": "admin"},
        )
        assert res.status_code == 201
        assert res.json()["agent_id"] == "SiliconBenchmarkLead"

        python_worker_1 = {
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
        }
        res = await client.post(
            "/api/v1/orchestrator/specs",
            json=python_worker_1,
            headers={"X-User-ID": "eng_lead_01", "X-User-Role": "admin"},
        )
        assert res.status_code == 201

        python_worker_2 = {
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
        }
        res = await client.post(
            "/api/v1/orchestrator/specs",
            json=python_worker_2,
            headers={"X-User-ID": "eng_lead_01", "X-User-Role": "admin"},
        )
        assert res.status_code == 201

        # 2. Register TypeScript Topology: AuditCompilerLead (SUPERVISOR) and worker
        ts_supervisor = {
            "agent_id": "AuditCompilerLead",
            "name": "Audit Compiler Lead",
            "description": "TypeScript compiler supervisor coordinating safety checks",
            "topology": "SUPERVISOR",
            "model": "claude-3-5-sonnet",
            "system_prompt": "You oversee compilation audit and verification.",
            "allowed_tools": ["tsc_check"],
            "sub_agents": ["TSSafetyVerifier"],
            "max_steps": 12,
            "timeout_seconds": 90.0,
        }
        res = await client.post(
            "/api/v1/orchestrator/specs",
            json=ts_supervisor,
            headers={"X-User-ID": "ts_lead_01", "X-User-Role": "admin"},
        )
        assert res.status_code == 201

        ts_worker = {
            "agent_id": "TSSafetyVerifier",
            "name": "TS Safety Verifier",
            "description": "Worker verifying type soundness and AST bounds",
            "topology": "WORKER",
            "model": "claude-3-5-sonnet",
            "system_prompt": "You verify type safety constraints.",
            "allowed_tools": ["ast_scan"],
            "sub_agents": [],
            "max_steps": 8,
            "timeout_seconds": 45.0,
        }
        res = await client.post(
            "/api/v1/orchestrator/specs",
            json=ts_worker,
            headers={"X-User-ID": "ts_lead_01", "X-User-Role": "admin"},
        )
        assert res.status_code == 201

        # 3. Discover and assert specs
        res = await client.get(
            "/api/v1/orchestrator/specs",
            headers={"X-User-ID": "eng_lead_01", "X-User-Role": "admin"},
        )
        assert res.status_code == 200
        registered_ids = [s["agent_id"] for s in res.json()]
        assert "SiliconBenchmarkLead" in registered_ids
        assert "MontyKernelProfiler" in registered_ids
        assert "RooflineAuditor" in registered_ids
        assert "AuditCompilerLead" in registered_ids
        assert "TSSafetyVerifier" in registered_ids


@pytest.mark.e2e
@pytest.mark.unauthenticated
@pytest.mark.asyncio
async def test_python_multi_agent_lifecycle_and_delegation(clean_e2e_registry):
    """Verify complete Python multi-agent lifecycle.

    - SiliconBenchmarkLead starts with root 4-tuple identity headers.
    - SiliconBenchmarkLead delegates to MontyKernelProfiler via POST /handoff.
    - Delegation preserves Actor-ID and Cost-Centre-ID, prefixes Session-ID.
    - SiliconBenchmarkLead delegates to RooflineAuditor.
    - Execution history contains step artifacts and outputs.
    """
    async with AsyncClient(
        transport=ASGITransport(app=control_plane_app),
        base_url="http://testserver",
    ) as client:
        # Pre-register specs
        specs = [
            {
                "agent_id": "SiliconBenchmarkLead",
                "name": "Silicon Benchmark Lead",
                "description": "Supervisor",
                "topology": "SUPERVISOR",
                "system_prompt": "Supervisor prompt",
                "sub_agents": ["MontyKernelProfiler", "RooflineAuditor"],
            },
            {
                "agent_id": "MontyKernelProfiler",
                "name": "Monty Kernel Profiler",
                "description": "Worker",
                "topology": "WORKER",
                "system_prompt": "Profiler prompt",
                "allowed_tools": ["execute_code"],
            },
            {
                "agent_id": "RooflineAuditor",
                "name": "Roofline Auditor",
                "description": "Worker",
                "topology": "WORKER",
                "system_prompt": "Auditor prompt",
                "allowed_tools": ["get_accelerator_specs"],
            },
        ]
        for spec in specs:
            res = await client.post(
                "/api/v1/orchestrator/specs",
                json=spec,
                headers={"X-User-ID": "usr_vortex_lead"},
            )
            assert res.status_code == 201

        headers = {
            "X-Actor-ID": "usr_vortex_lead",
            "X-User-ID": "usr_vortex_lead",
            "X-Agent-ID": "SiliconBenchmarkLead",
            "X-Cost-Centre-ID": "silicon-perf-lab",
            "X-Session-ID": "sess-benchmark-flow-001",
        }

        # 1. Start supervisor run
        run_payload = {
            "prompt": "Evaluate GEMM kernel scaling across matrix dimensions [256, 1024, 2048]",
            "context": {"target_device": "vortex-npu-v2"},
        }
        res = await client.post(
            "/api/v1/orchestrator/runs/SiliconBenchmarkLead",
            json=run_payload,
            headers=headers,
        )
        assert res.status_code == 200
        lead_session = res.json()
        assert lead_session["status"] == AgentExecutionStatus.COMPLETED
        assert lead_session["session_id"] == "sess-benchmark-flow-001"
        assert lead_session["composite_key"]["actor_id"] == "usr_vortex_lead"
        assert lead_session["composite_key"]["cost_centre_id"] == "silicon-perf-lab"

        # 2. Handoff to MontyKernelProfiler
        handoff_1 = {
            "parent_session_id": "sess-benchmark-flow-001",
            "caller_agent_id": "SiliconBenchmarkLead",
            "target_agent_id": "MontyKernelProfiler",
            "task_instructions": "Profile kernel matrix multiplication on NPU",
            "context_data": {"matrix_dim": 2048, "precision": "fp32"},
        }
        res_handoff_1 = await client.post(
            "/api/v1/orchestrator/handoff",
            json=handoff_1,
            headers=headers,
        )
        assert res_handoff_1.status_code == 200
        profiler_session = res_handoff_1.json()
        assert profiler_session["status"] == AgentExecutionStatus.COMPLETED
        assert profiler_session["composite_key"]["actor_id"] == "usr_vortex_lead"
        assert profiler_session["composite_key"]["cost_centre_id"] == "silicon-perf-lab"
        assert profiler_session["composite_key"]["agent_id"] == "MontyKernelProfiler"
        assert profiler_session["composite_key"]["session_id"].startswith("sess-benchmark-flow-001-MontyKernelProfiler-")
        assert len(profiler_session["history"]) > 0
        assert profiler_session["history"][0]["tool_call_name"] == "execute_code"

        # 3. Handoff to RooflineAuditor
        handoff_2 = {
            "parent_session_id": "sess-benchmark-flow-001",
            "caller_agent_id": "SiliconBenchmarkLead",
            "target_agent_id": "RooflineAuditor",
            "task_instructions": "Calculate operational intensity and compare with accelerator specs",
            "context_data": {"gflops": 128.0, "bandwidth_gbps": 64.0},
        }
        res_handoff_2 = await client.post(
            "/api/v1/orchestrator/handoff",
            json=handoff_2,
            headers=headers,
        )
        assert res_handoff_2.status_code == 200
        auditor_session = res_handoff_2.json()
        assert auditor_session["status"] == AgentExecutionStatus.COMPLETED
        assert auditor_session["composite_key"]["actor_id"] == "usr_vortex_lead"
        assert auditor_session["composite_key"]["cost_centre_id"] == "silicon-perf-lab"
        assert auditor_session["composite_key"]["agent_id"] == "RooflineAuditor"
        assert auditor_session["composite_key"]["session_id"].startswith("sess-benchmark-flow-001-RooflineAuditor-")


@pytest.mark.e2e
@pytest.mark.unauthenticated
@pytest.mark.asyncio
async def test_typescript_multi_agent_lifecycle_and_cancellation(clean_e2e_registry):
    """Verify TypeScript agent lifecycle, handoff, and session cancellation."""
    async with AsyncClient(
        transport=ASGITransport(app=control_plane_app),
        base_url="http://testserver",
    ) as client:
        # Pre-register specs
        specs = [
            {
                "agent_id": "AuditCompilerLead",
                "name": "Audit Compiler Lead",
                "description": "Supervisor",
                "topology": "SUPERVISOR",
                "system_prompt": "Supervisor prompt",
                "sub_agents": ["TSSafetyVerifier"],
            },
            {
                "agent_id": "TSSafetyVerifier",
                "name": "TS Safety Verifier",
                "description": "Worker",
                "topology": "WORKER",
                "system_prompt": "Verifier prompt",
                "allowed_tools": ["ast_scan"],
            },
        ]
        for spec in specs:
            res = await client.post(
                "/api/v1/orchestrator/specs",
                json=spec,
                headers={"X-User-ID": "usr_ts_auditor"},
            )
            assert res.status_code == 201

        headers = {
            "X-Actor-ID": "usr_ts_auditor",
            "X-User-ID": "usr_ts_auditor",
            "X-Agent-ID": "AuditCompilerLead",
            "X-Cost-Centre-ID": "ts-platform-eng",
            "X-Session-ID": "sess-ts-audit-900",
        }

        # 1. Handoff to TSSafetyVerifier
        handoff_payload = {
            "parent_session_id": "sess-ts-audit-900",
            "caller_agent_id": "AuditCompilerLead",
            "target_agent_id": "TSSafetyVerifier",
            "task_instructions": "Verify soundness of type declarations in compiler output",
            "context_data": {"ast_nodes": 450},
        }
        res_handoff = await client.post(
            "/api/v1/orchestrator/handoff",
            json=handoff_payload,
            headers=headers,
        )
        assert res_handoff.status_code == 200
        worker_session = res_handoff.json()
        assert worker_session["status"] == AgentExecutionStatus.COMPLETED
        worker_session_id = worker_session["session_id"]

        # 2. Query session state by session_id
        res_session = await client.get(
            f"/api/v1/orchestrator/sessions/{worker_session_id}",
            headers=headers,
        )
        assert res_session.status_code == 200
        assert res_session.json()["session_id"] == worker_session_id

        # 3. Graceful cancellation
        cancel_res = await client.post(
            f"/api/v1/orchestrator/sessions/{worker_session_id}/cancel",
            headers=headers,
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == AgentExecutionStatus.CANCELLED

        # 4. Verify cancelled status is persisted
        verify_res = await client.get(
            f"/api/v1/orchestrator/sessions/{worker_session_id}",
            headers=headers,
        )
        assert verify_res.status_code == 200
        assert verify_res.json()["status"] == AgentExecutionStatus.CANCELLED


@pytest.mark.e2e
@pytest.mark.unauthenticated
@pytest.mark.asyncio
async def test_bidirectional_cross_ecosystem_handoff(clean_e2e_registry):
    """Verify bidirectional cross-ecosystem delegation and boundary enforcement.

    Registers 4 agent specs spanning Python and TypeScript ecosystems:
    - SiliconBenchmarkLead (SUPERVISOR, sub_agents: ["MontyKernelProfiler", "RooflineAuditor", "TSSafetyVerifier"])
    - MontyKernelProfiler (WORKER)
    - RooflineAuditor (WORKER)
    - AuditCompilerLead (SUPERVISOR, sub_agents: ["TSSafetyVerifier", "MontyKernelProfiler"])
    - TSSafetyVerifier (WORKER)

    Step 1: Python Supervisor -> TypeScript Worker handoff (SiliconBenchmarkLead -> TSSafetyVerifier)
      - Asserts HTTP 200, status COMPLETED.
      - Asserts 4-tuple key propagation: actor_id and cost_centre_id preserved,
        session_id branches hierarchically.
    Step 2: TypeScript Supervisor -> Python Worker handoff (AuditCompilerLead -> MontyKernelProfiler)
      - Asserts HTTP 200, status COMPLETED.
      - Asserts 4-tuple key propagation: actor_id and cost_centre_id preserved,
        session_id branches hierarchically.
    Step 3: Unauthorized cross-delegation attempt
      - AuditCompilerLead -> RooflineAuditor (not in AuditCompilerLead sub_agents).
      - Asserts HTTP 400 Bad Request.
    """
    async with AsyncClient(
        transport=ASGITransport(app=control_plane_app),
        base_url="http://testserver",
    ) as client:
        # Register all 4 agent specifications (5 specs total including all roles)
        specs = [
            {
                "agent_id": "SiliconBenchmarkLead",
                "name": "Silicon Benchmark Lead",
                "description": "Python Supervisor managing hardware benchmarks and safety checks",
                "topology": "SUPERVISOR",
                "system_prompt": "Supervisor prompt",
                "sub_agents": ["MontyKernelProfiler", "RooflineAuditor", "TSSafetyVerifier"],
            },
            {
                "agent_id": "MontyKernelProfiler",
                "name": "Monty Kernel Profiler",
                "description": "Python Worker executing tensor kernel operations",
                "topology": "WORKER",
                "system_prompt": "Profiler prompt",
                "allowed_tools": ["execute_code"],
            },
            {
                "agent_id": "RooflineAuditor",
                "name": "Roofline Auditor",
                "description": "Python Worker auditing operational intensity",
                "topology": "WORKER",
                "system_prompt": "Auditor prompt",
                "allowed_tools": ["get_accelerator_specs"],
            },
            {
                "agent_id": "AuditCompilerLead",
                "name": "Audit Compiler Lead",
                "description": "TypeScript Supervisor coordinating audit and profiling",
                "topology": "SUPERVISOR",
                "system_prompt": "TypeScript supervisor prompt",
                "sub_agents": ["TSSafetyVerifier", "MontyKernelProfiler"],
            },
            {
                "agent_id": "TSSafetyVerifier",
                "name": "TS Safety Verifier",
                "description": "TypeScript Worker verifying type safety constraints",
                "topology": "WORKER",
                "system_prompt": "Verifier prompt",
                "allowed_tools": ["ast_scan"],
            },
        ]

        for spec in specs:
            res = await client.post(
                "/api/v1/orchestrator/specs",
                json=spec,
                headers={"X-User-ID": "admin_user", "X-User-Role": "admin"},
            )
            assert res.status_code == 201

        # Step 1: Python Supervisor -> TypeScript Worker handoff
        python_lead_headers = {
            "X-Actor-ID": "usr_vortex_lead",
            "X-User-ID": "usr_vortex_lead",
            "X-Agent-ID": "SiliconBenchmarkLead",
            "X-Cost-Centre-ID": "silicon-perf-lab",
            "X-Session-ID": "sess-benchmark-flow-001",
        }
        handoff_py_to_ts = {
            "parent_session_id": "sess-benchmark-flow-001",
            "caller_agent_id": "SiliconBenchmarkLead",
            "target_agent_id": "TSSafetyVerifier",
            "task_instructions": "Verify soundness of kernel bindings generated by silicon compiler",
            "context_data": {"binding_type": "npu_tensor_bridge"},
        }
        res_py_to_ts = await client.post(
            "/api/v1/orchestrator/handoff",
            json=handoff_py_to_ts,
            headers=python_lead_headers,
        )
        assert res_py_to_ts.status_code == 200
        py_to_ts_session = res_py_to_ts.json()
        assert py_to_ts_session["status"] == AgentExecutionStatus.COMPLETED
        assert py_to_ts_session["composite_key"]["actor_id"] == "usr_vortex_lead"
        assert py_to_ts_session["composite_key"]["cost_centre_id"] == "silicon-perf-lab"
        assert py_to_ts_session["composite_key"]["agent_id"] == "TSSafetyVerifier"
        assert py_to_ts_session["composite_key"]["session_id"].startswith("sess-benchmark-flow-001-TSSafetyVerifier-")

        # Step 2: TypeScript Supervisor -> Python Worker handoff
        ts_lead_headers = {
            "X-Actor-ID": "usr_ts_auditor",
            "X-User-ID": "usr_ts_auditor",
            "X-Agent-ID": "AuditCompilerLead",
            "X-Cost-Centre-ID": "ts-platform-eng",
            "X-Session-ID": "sess-ts-audit-900",
        }
        handoff_ts_to_py = {
            "parent_session_id": "sess-ts-audit-900",
            "caller_agent_id": "AuditCompilerLead",
            "target_agent_id": "MontyKernelProfiler",
            "task_instructions": "Profile native tensor ops invoked from compiler test harness",
            "context_data": {"benchmark_target": "npu_jit_kernel"},
        }
        res_ts_to_py = await client.post(
            "/api/v1/orchestrator/handoff",
            json=handoff_ts_to_py,
            headers=ts_lead_headers,
        )
        assert res_ts_to_py.status_code == 200
        ts_to_py_session = res_ts_to_py.json()
        assert ts_to_py_session["status"] == AgentExecutionStatus.COMPLETED
        assert ts_to_py_session["composite_key"]["actor_id"] == "usr_ts_auditor"
        assert ts_to_py_session["composite_key"]["cost_centre_id"] == "ts-platform-eng"
        assert ts_to_py_session["composite_key"]["agent_id"] == "MontyKernelProfiler"
        assert ts_to_py_session["composite_key"]["session_id"].startswith("sess-ts-audit-900-MontyKernelProfiler-")

        # Step 3: Unauthorized cross-delegation attempt
        unauthorized_handoff = {
            "parent_session_id": "sess-ts-audit-900",
            "caller_agent_id": "AuditCompilerLead",
            "target_agent_id": "RooflineAuditor",
            "task_instructions": "Attempt unauthorized delegation to RooflineAuditor",
            "context_data": {},
        }
        res_unauthorized = await client.post(
            "/api/v1/orchestrator/handoff",
            json=unauthorized_handoff,
            headers=ts_lead_headers,
        )
        assert res_unauthorized.status_code == 400

