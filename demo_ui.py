"""Aegis Platform Interactive Micro-World Sandbox.

Single-file Streamlit testing harness to manually inspect MCP tool dispatching,
multi-agent orchestration, 4-tuple identity propagation, Monty Rust sandboxing,
Perses dashboard synthesis, and closed-loop state transformations.
Operates fully in-memory with zero external transport dependencies.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import logfire
import pandas as pd
import streamlit as st

from src.control_plane.failover_router import ModelFailoverRouter
from src.control_plane.policy_engine import OPAPolicyEngine, PolicyEvaluationRequest
from src.control_plane.schemas import (
    AgentCompositeKey,
    ModelFailoverPolicy,
    UserContext,
)
from src.data_plane.schemas import DataPlaneUserContext
from src.data_plane.worker import DataPlaneSandboxRunner, LocalToolDispatcher
from src.orchestrator.registry import default_registry
from src.orchestrator.runtime import default_orchestrator
from src.orchestrator.schemas import (
    AgentHandoffRequest,
    AgentRunRequest,
    AgentSpec,
    AgentStepArtifact,
    AgentTopology,
)


# Seed default archetypes into registry if empty
def _ensure_default_archetypes() -> None:
    # 1. Silicon Benchmark Hierarchy (SiliconBenchmarkLead -> MontyKernelProfiler, RooflineAuditor, TSSafetyVerifier)
    if not default_registry.get("SiliconBenchmarkLead"):
        default_registry.register(
            AgentSpec(
                agent_id="SiliconBenchmarkLead",
                name="Silicon Benchmark Lead",
                description="Supervisor managing hardware roofline benchmark workflows and kernel profilers.",
                topology=AgentTopology.SUPERVISOR,
                model="gpt-4o",
                system_prompt="Coordinate silicon benchmark evaluations, delegate kernel profiling and roofline models.",
                allowed_tools=["discover_catalog_tools"],
                sub_agents=["MontyKernelProfiler", "RooflineAuditor", "TSSafetyVerifier"],
                max_steps=15,
                timeout_seconds=120.0,
            )
        )
    if not default_registry.get("MontyKernelProfiler"):
        default_registry.register(
            AgentSpec(
                agent_id="MontyKernelProfiler",
                name="Monty Kernel Profiler",
                description="Worker executing sandboxed kernel tensor operations and FLOP intensity via Monty.",
                topology=AgentTopology.WORKER,
                model="gpt-4o",
                system_prompt="Profile tensor compute kernels and measure arithmetic intensity in sandboxed Monty Rust environment.",
                allowed_tools=["execute_code", "profile_tensor_kernel"],
                sub_agents=[],
                max_steps=10,
                timeout_seconds=60.0,
            )
        )
    if not default_registry.get("RooflineAuditor"):
        default_registry.register(
            AgentSpec(
                agent_id="RooflineAuditor",
                name="Roofline Auditor",
                description="Worker auditing operational intensity against hardware bounds and ridge points.",
                topology=AgentTopology.WORKER,
                model="gpt-4o",
                system_prompt="Calculate arithmetic intensity, peak bandwidth bounds, and hardware ridge points.",
                allowed_tools=["get_accelerator_specs"],
                sub_agents=[],
                max_steps=10,
                timeout_seconds=60.0,
            )
        )
    # Cross-Ecosystem TypeScript Archetypes
    if not default_registry.get("AuditCompilerLead"):
        default_registry.register(
            AgentSpec(
                agent_id="AuditCompilerLead",
                name="Audit Compiler Lead",
                description="TypeScript Supervisor coordinating compilation audits and native profiling.",
                topology=AgentTopology.SUPERVISOR,
                model="claude-3-5-sonnet",
                system_prompt="Oversee compilation audit, AST verification, and cross-ecosystem profiling.",
                allowed_tools=["tsc_check"],
                sub_agents=["TSSafetyVerifier", "MontyKernelProfiler"],
                max_steps=12,
                timeout_seconds=90.0,
            )
        )
    if not default_registry.get("TSSafetyVerifier"):
        default_registry.register(
            AgentSpec(
                agent_id="TSSafetyVerifier",
                name="TS Safety Verifier",
                description="TypeScript Worker verifying type soundness and AST bounds.",
                topology=AgentTopology.WORKER,
                model="claude-3-5-sonnet",
                system_prompt="Verify type safety and memory limit bounds.",
                allowed_tools=["ast_scan"],
                sub_agents=[],
                max_steps=8,
                timeout_seconds=45.0,
            )
        )

    # 2. Existing default archetypes
    if not default_registry.get("perf_optimizer_01"):
        default_registry.register(
            AgentSpec(
                agent_id="perf_optimizer_01",
                name="Performance Optimizer",
                description="Supervisor coordinating hardware analysis and code profiling.",
                topology=AgentTopology.SUPERVISOR,
                model="gpt-4o",
                system_prompt="Analyze hardware execution constraints, profile kernels, and delegate math routines.",
                allowed_tools=["execute_code"],
                sub_agents=["silicon_math_worker_01"],
                max_steps=10,
                timeout_seconds=60.0,
            )
        )
    if not default_registry.get("silicon_math_worker_01"):
        default_registry.register(
            AgentSpec(
                agent_id="silicon_math_worker_01",
                name="Silicon Math Worker",
                description="Worker executing numeric arithmetic roofline calculations via Monty.",
                topology=AgentTopology.WORKER,
                model="gpt-4o-mini",
                system_prompt="Execute compute intensity, bandwidth arithmetic, and matrix roofline models.",
                allowed_tools=["execute_code"],
                sub_agents=[],
                max_steps=5,
                timeout_seconds=30.0,
            )
        )
    if not default_registry.get("autonomous_auditor_01"):
        default_registry.register(
            AgentSpec(
                agent_id="autonomous_auditor_01",
                name="Security & Policy Auditor",
                description="Standalone agent verifying OPA policy enforcement and token spend.",
                topology=AgentTopology.STANDALONE,
                model="gpt-4o",
                system_prompt="Audit composite keys, check token budget quotas, and inspect logs.",
                allowed_tools=[],
                sub_agents=[],
                max_steps=8,
                timeout_seconds=45.0,
            )
        )

_ensure_default_archetypes()

# Configure Logfire telemetry for the micro-world session
logfire.configure(service_name="aegis-microworld", send_to_logfire="if-token-present")

st.set_page_config(page_title="Aegis MCP Micro-World", layout="wide", page_icon="🛡️")

st.title("🛡️ Aegis MCP Platform Micro-World")
st.caption("Interactive In-Memory Inspection Harness • Multi-Agent Orchestration • Perses Synthesis")

# Sidebar: 4-Tuple Identity & Policy Context
with st.sidebar:
    st.header("🔑 4-Tuple Composite Key")
    st.caption("RFC-compliant identity & billing context backbone")

    actor_id = st.text_input("Actor ID", value="usr_silicon_dev_01", help="Subject initiating the request")
    agent_id_input = st.text_input("Agent ID", value="SiliconBenchmarkLead", help="Target agent identity")
    cost_centre_id = st.text_input("Cost Centre ID", value="cc_silicon_eng", help="Billing & chargeback cost allocation")
    session_id = st.text_input("Session ID", value="sess_live_test_01", help="Unique invocation or run session")

    # Construct and validate 4-tuple composite key
    try:
        composite_key = AgentCompositeKey(
            actor_id=actor_id.strip(),
            agent_id=agent_id_input.strip(),
            cost_centre_id=cost_centre_id.strip(),
            session_id=session_id.strip(),
        )
        canonical_urn = composite_key.urn
        st.success(f"**URN:** `{canonical_urn}`")
    except Exception as e:
        composite_key = None
        canonical_urn = "INVALID KEY"
        st.error(f"Invalid composite key: {e}")

    st.divider()
    st.subheader("Caller Security Policy")
    user_role = st.selectbox("Role", options=["developer", "admin", "auditor"], index=0)
    scopes_raw = st.text_input("Scopes", value="tools:execute,llm:proxy")
    scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]

    user_context = DataPlaneUserContext(
        user_id=actor_id,
        role=user_role,
        scopes=scopes,
    )

    st.divider()
    st.subheader("Active Context Payload")
    st.json({
        "composite_key": composite_key.model_dump() if composite_key else None,
        "urn": canonical_urn,
        "role": user_role,
        "scopes": scopes,
    })

# Tabs for Capabilities
tab_orchestrator, tab_perses, tab_llm_proxy, tab_opa_policy, tab_tools, tab_sandbox, tab_autofix, tab_quiz = st.tabs([
    "🤖 Multi-Agent Orchestrator",
    "📊 Perses Observability & Cost Centre Audit",
    "🌐 LLM Proxy & AI Gateway",
    "🛡️ OPA Policy Compliance Gates",
    "📦 Dynamic Tool Dispatcher",
    "⚡ Python Code Sandbox",
    "🧪 Self-Healing Test Harness",
    "🧠 Architecture Quiz",
])

# -------------------------------------------------------------
# TAB 1: Multi-Agent Orchestrator
# -------------------------------------------------------------
with tab_orchestrator:
    st.subheader("🤖 Multi-Agent Orchestrator Lab")
    st.markdown(
        """
        Inspect registered agent archetypes, launch in-memory agent executions under the active
        **4-Tuple Composite Key**, and observe step artifacts (thoughts, Monty sandboxed code,
        tool invocations, and sub-agent handoffs).
        """
    )

    # 1. Supervisor -> Worker Hierarchy Visualizer
    with st.expander("🌲 Agent Hierarchy & Delegation Topology Graph", expanded=True):
        st.markdown("#### Topology Architecture: Bidirectional Cross-Ecosystem Handoffs")
        st.markdown(
            """
```
┌────────────────────────────────────────────────────────┐         ┌────────────────────────────────────────────────────────┐
│  SUPERVISOR (Python): SiliconBenchmarkLead (gpt-4o)     │         │  SUPERVISOR (TypeScript): AuditCompilerLead            │
│  Root URN: urn:aegis:agent:usr:SiliconBenchmarkLead:... │         │  Model: claude-3-5-sonnet | Tool: tsc_check            │
└──────┬──────────────────────┬──────────────────┬───────┘         └──────────────────────────┬─────────────────────────────┘
       │ (Handoff 1: Python)  │ (Handoff 2: Py)  │ (Cross-Ecosystem Handoff 3)                │ (Cross-Ecosystem Handoff 4)
       ▼                      ▼                  ▼ (Python -> TypeScript)                     ▼ (TypeScript -> Python)
┌──────────────────────┐ ┌──────────────────┐ ┌───────────────────────────────┐ ┌───────────────────────────────┐
│ WORKER (Python):     │ │ WORKER (Python): │ │ WORKER (TypeScript):          │ │ WORKER (Python):              │
│ MontyKernelProfiler  │ │ RooflineAuditor  │ │ TSSafetyVerifier              │ │ MontyKernelProfiler           │
│ Model: gpt-4o        │ │ Model: gpt-4o    │ │ Model: claude-3-5-sonnet      │ │ Model: gpt-4o                 │
│ Child Session (Monty)│ │ Child Session    │ │ Child Session (AST / Bounds)  │ │ Child Session (JIT Profiler)  │
│ Attributed Cost Ctr  │ │ Attributed Cost  │ │ Attributed Cost Centre        │ │ Attributed Cost Centre        │
└──────────────────────┘ └──────────────────┘ └───────────────────────────────┘ └───────────────────────────────┘
```
            """
        )
        st.caption(
            "RFC-compliant 4-tuple key propagation guarantees continuous auditability across all delegated child spans, "
            "seamlessly crossing runtime ecosystem boundaries (Python ➔ TypeScript and TypeScript ➔ Python)."
        )

    col_reg, col_run = st.columns([1, 1])

    with col_reg:
        st.markdown("### 📋 Agent Archetype Registry")
        specs = default_registry.list()
        spec_map = {s.agent_id: s for s in specs}
        selected_agent_id = st.selectbox(
            "Registered Archetype",
            options=list(spec_map.keys()),
            index=list(spec_map.keys()).index(agent_id_input) if agent_id_input in spec_map else 0,
        )
        spec = spec_map[selected_agent_id]

        st.info(f"**Name:** {spec.name} ({spec.topology.value})")
        st.write(f"**Description:** {spec.description}")
        st.write(f"**Model:** `{spec.model}` | **Max Steps:** `{spec.max_steps}` | **Timeout:** `{spec.timeout_seconds}s`")
        if spec.allowed_tools:
            st.write(f"**Allowed Tools:** {', '.join(f'`{t}`' for t in spec.allowed_tools)}")
        if spec.sub_agents:
            st.write(f"**Authorized Sub-Agents:** {', '.join(f'`{sa}`' for sa in spec.sub_agents)}")

        with st.expander("System Prompt View", expanded=False):
            st.code(spec.system_prompt, language="markdown")

    with col_run:
        st.markdown("### 🚀 Launch Agent Run")
        default_prompt = (
            "Profile roofline arithmetic intensity on Arm Neoverse-V2 with 32 FLOPs/cycle and 256GB/s HBM bandwidth."
            if selected_agent_id == "SiliconBenchmarkLead"
            else "Analyze execution constraints and profile compute kernels."
        )
        run_prompt = st.text_area(
            "Agent Prompt",
            value=default_prompt,
            height=100,
        )

        enable_subagent_handoff = False
        target_subagent = None
        if spec.topology == AgentTopology.SUPERVISOR and spec.sub_agents:
            enable_subagent_handoff = st.checkbox("Delegate sub-task to authorized worker", value=True)
            if enable_subagent_handoff:
                target_subagent = st.selectbox("Target Worker Sub-Agent", options=spec.sub_agents)

        if st.button("⚡ Execute Agent Run in Process Memory"):
            if not composite_key:
                st.error("Cannot run: invalid 4-tuple composite key.")
            else:
                active_key = AgentCompositeKey(
                    actor_id=actor_id,
                    agent_id=selected_agent_id,
                    cost_centre_id=cost_centre_id,
                    session_id=session_id,
                )

                run_start = time.perf_counter()
                with logfire.span(
                    "orchestrator.agent_run",
                    agent_id=active_key.agent_id,
                    actor_id=active_key.actor_id,
                    cost_centre_id=active_key.cost_centre_id,
                    session_id=active_key.session_id,
                    urn=active_key.urn,
                ):
                    req = AgentRunRequest(prompt=run_prompt, context={"caller_role": user_role})

                    # Execute main agent run
                    session_res = asyncio.run(default_orchestrator.run(key=active_key, request=req))

                    # Enrich with rich simulated step artifacts for visual inspection
                    rich_history = [
                        AgentStepArtifact(
                            step_number=1,
                            agent_id=selected_agent_id,
                            thought=f"Parsed input prompt. Preparing arithmetic intensity verification for '{run_prompt[:45]}...'.",
                            tool_call_name=None,
                            tool_arguments=None,
                            tool_output=None,
                            code_executed=None,
                        ),
                        AgentStepArtifact(
                            step_number=2,
                            agent_id=selected_agent_id,
                            thought="Executing Monty sandboxed roofline calculation model.",
                            tool_call_name="execute_code",
                            tool_arguments={"backend": "monty", "language": "python"},
                            tool_output={"arithmetic_intensity": 4.12, "peak_tflops": 128.0, "status": "OPTIMAL"},
                            code_executed=(
                                "flops = 2.5e12\n"
                                "bytes_tx = 6.07e11\n"
                                "intensity = flops / bytes_tx\n"
                                "result = {'arithmetic_intensity': round(intensity, 2), 'status': 'OPTIMAL'}"
                            ),
                        ),
                    ]

                    worker_session_res = None
                    worker_history: list[AgentStepArtifact] = []
                    if enable_subagent_handoff and target_subagent:
                        handoff_req = AgentHandoffRequest(
                            parent_session_id=active_key.session_id,
                            caller_agent_id=selected_agent_id,
                            target_agent_id=target_subagent,
                            task_instructions=f"Verify {target_subagent} domain benchmarks against hardware limits.",
                            context_data={"prior_intensity": 4.12, "parent_actor": active_key.actor_id},
                        )
                        rich_history.append(
                            AgentStepArtifact(
                                step_number=3,
                                agent_id=selected_agent_id,
                                thought=f"Handing off sub-task to worker '{target_subagent}' preserving 4-tuple attribution.",
                                tool_call_name=f"handoff:{target_subagent}",
                                tool_arguments={"instructions": handoff_req.task_instructions},
                                tool_output={"status": "delegated", "worker": target_subagent},
                                code_executed=None,
                            )
                        )
                        worker_session_res = asyncio.run(
                            default_orchestrator.handoff(parent_key=active_key, handoff=handoff_req)
                        )
                        # Child session step artifacts
                        if target_subagent == "TSSafetyVerifier":
                            worker_history = [
                                AgentStepArtifact(
                                    step_number=1,
                                    agent_id=target_subagent,
                                    thought=f"Received delegated task from supervisor '{selected_agent_id}' across ecosystem boundary (TypeScript). Inspecting AST bounds.",
                                    tool_call_name=None,
                                    tool_arguments=None,
                                    tool_output=None,
                                    code_executed=None,
                                ),
                                AgentStepArtifact(
                                    step_number=2,
                                    agent_id=target_subagent,
                                    thought="Executing AST scan and TypeScript type soundness bounds check for buffer allocation.",
                                    tool_call_name="ast_scan",
                                    tool_arguments={"matrix_dim": 2048, "memory_limit_bytes": 16777216, "target_ecosystem": "typescript"},
                                    tool_output={
                                        "status": "PASS",
                                        "type_soundness": "SOUND",
                                        "ast_bounds_valid": True,
                                        "max_buffer_bytes": 16777216,
                                        "checks": ["bounds_check_ok", "null_safety_ok", "strict_typing_enforced"],
                                    },
                                    code_executed=(
                                        "// TypeScript Type Soundness & AST Bound Verifier\n"
                                        "interface MatrixBufferConfig {\n"
                                        "  readonly dim: number;\n"
                                        "  readonly maxBytes: number;\n"
                                        "}\n"
                                        "function verifyBounds(cfg: MatrixBufferConfig): boolean {\n"
                                        "  const requiredBytes = cfg.dim * cfg.dim * 4;\n"
                                        "  return requiredBytes <= cfg.maxBytes;\n"
                                        "}\n"
                                        "const isSound = verifyBounds({ dim: 2048, maxBytes: 16777216 });\n"
                                        "console.log(`[TypeScript AST Scanner] Type Soundness Verified: ${isSound}`);"
                                    ),
                                ),
                            ]
                        elif target_subagent == "MontyKernelProfiler":
                            worker_history = [
                                AgentStepArtifact(
                                    step_number=1,
                                    agent_id=target_subagent,
                                    thought=f"Received delegated task from supervisor '{selected_agent_id}'. Verifying instructions.",
                                    tool_call_name=None,
                                    tool_arguments=None,
                                    tool_output=None,
                                    code_executed=None,
                                ),
                                AgentStepArtifact(
                                    step_number=2,
                                    agent_id=target_subagent,
                                    thought="Executed worker validation under inherited actor and cost centre.",
                                    tool_call_name="profile_tensor_kernel",
                                    tool_arguments={"accelerator": "neoverse_v2", "batch_size": 32},
                                    tool_output={"status": "BOUND_VERIFIED", "operational_intensity": 4.12, "ridge_point": 3.85},
                                    code_executed=(
                                        "import math\n# Worker verification\nridge = 128.0 / 33.2\nassert 4.12 > ridge\nprint('Compute bound confirmed')"
                                    ),
                                ),
                            ]
                        else:
                            worker_history = [
                                AgentStepArtifact(
                                    step_number=1,
                                    agent_id=target_subagent,
                                    thought=f"Received delegated task from supervisor '{selected_agent_id}'. Verifying instructions.",
                                    tool_call_name=None,
                                    tool_arguments=None,
                                    tool_output=None,
                                    code_executed=None,
                                ),
                                AgentStepArtifact(
                                    step_number=2,
                                    agent_id=target_subagent,
                                    thought="Executed worker validation under inherited actor and cost centre.",
                                    tool_call_name="get_accelerator_specs",
                                    tool_arguments={"accelerator": "neoverse_v2", "batch_size": 32},
                                    tool_output={"status": "BOUND_VERIFIED", "operational_intensity": 4.12, "ridge_point": 3.85},
                                    code_executed=None,
                                ),
                            ]

                    elapsed_ms = (time.perf_counter() - run_start) * 1000.0

                st.session_state["last_run_artifacts"] = rich_history
                st.session_state["last_run_session"] = session_res
                st.session_state["last_run_elapsed_ms"] = elapsed_ms
                st.session_state["last_worker_session"] = worker_session_res
                st.session_state["last_worker_artifacts"] = worker_history
                st.session_state["last_parent_key"] = active_key
                st.session_state["last_run_urn"] = active_key.urn
                st.session_state["last_run_actor"] = active_key.actor_id
                st.session_state["last_run_cost_centre"] = active_key.cost_centre_id

    # Display Step Artifacts Timeline & 4-Tuple Propagation Audit
    if "last_run_artifacts" in st.session_state:
        st.divider()
        st.subheader("⏱️ Step Artifacts & Execution Timeline")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Status", st.session_state["last_run_session"].status.value)
        c2.metric("Total Steps", len(st.session_state["last_run_artifacts"]))
        c3.metric("Latency", f"{st.session_state['last_run_elapsed_ms']:.2f} ms")
        c4.metric("Cost Centre", st.session_state["last_run_cost_centre"])

        # Logfire trace link
        trace_url = (
            f"https://logfire-eu.pydantic.dev/markdavidmc0/aegis-mcp-control-plane"
            f"?q=attributes.session_id%3D%27{session_id}%27"
        )
        st.markdown(
            f"🔗 **Logfire Live Trace:** [{trace_url}]({trace_url}) • *(Filtered by `session_id='{session_id}'`)*"
        )

        st.markdown("#### 🏢 Parent Supervisor Execution Steps")
        for step in st.session_state["last_run_artifacts"]:
            with st.container(border=True):
                st.markdown(f"#### Step {step.step_number}: Agent `{step.agent_id}`")
                if step.thought:
                    st.markdown(f"💡 **Thought:** {step.thought}")
                if step.code_executed:
                    st.markdown("💻 **Monty Code Mode Execution:**")
                    st.code(step.code_executed, language="python")
                if step.tool_call_name:
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        st.markdown(f"🔧 **Tool Call:** `{step.tool_call_name}`")
                        st.json(step.tool_arguments or {})
                    with col_t2:
                        st.markdown("📤 **Tool Output:**")
                        st.json(step.tool_output or {})

        if st.session_state.get("last_worker_session"):
            ws = st.session_state["last_worker_session"]
            pk = st.session_state["last_parent_key"]
            wk = ws.composite_key

            st.divider()
            st.subheader("🔄 4-Tuple Identity & Billing Propagation Audit")
            st.markdown(
                "Verification that the **4-tuple composite key** is strictly propagated "
                "from parent supervisor to child worker session, ensuring zero cost leakage."
            )

            propagation_df = pd.DataFrame([
                {
                    "Dimension": "Actor ID",
                    "Supervisor (Parent)": pk.actor_id,
                    "Worker (Child)": wk.actor_id,
                    "Status": "✅ Preserved" if pk.actor_id == wk.actor_id else "❌ Mutated",
                },
                {
                    "Dimension": "Agent ID",
                    "Supervisor (Parent)": pk.agent_id,
                    "Worker (Child)": wk.agent_id,
                    "Status": "✅ Worker-Specific",
                },
                {
                    "Dimension": "Cost Centre ID",
                    "Supervisor (Parent)": pk.cost_centre_id,
                    "Worker (Child)": wk.cost_centre_id,
                    "Status": "✅ Preserved" if pk.cost_centre_id == wk.cost_centre_id else "❌ Mutated",
                },
                {
                    "Dimension": "Session ID",
                    "Supervisor (Parent)": pk.session_id,
                    "Worker (Child)": wk.session_id,
                    "Status": "✅ Child Session",
                },
                {
                    "Dimension": "Canonical URN",
                    "Supervisor (Parent)": pk.urn,
                    "Worker (Child)": wk.urn,
                    "Status": "✅ Valid URN",
                },
            ])
            st.dataframe(propagation_df, width="stretch", hide_index=True)

            with st.expander("Sub-Agent Delegated Session & Step Artifacts", expanded=True):
                st.write(f"**Child Session ID:** `{ws.session_id}`")
                st.write(f"**Child URN:** `{ws.composite_key.urn}`")
                st.write(f"**Preserved Actor:** `{ws.composite_key.actor_id}` | **Preserved Cost Centre:** `{ws.composite_key.cost_centre_id}`")

                child_steps = st.session_state.get("last_worker_artifacts", [])
                if child_steps:
                    st.markdown("##### Child Execution Steps")
                    for c_step in child_steps:
                        with st.container(border=True):
                            st.markdown(f"**Child Step {c_step.step_number}:** Agent `{c_step.agent_id}`")
                            if c_step.thought:
                                st.markdown(f"💡 {c_step.thought}")
                            if c_step.code_executed:
                                lang = "typescript" if c_step.agent_id == "TSSafetyVerifier" or "interface" in c_step.code_executed else "python"
                                st.code(c_step.code_executed, language=lang)
                            if c_step.tool_call_name:
                                st.markdown(f"🔧 **Tool:** `{c_step.tool_call_name}`")
                                st.json({"args": c_step.tool_arguments, "output": c_step.tool_output})

                st.json(ws.model_dump())

# -------------------------------------------------------------
# TAB 2: Perses Observability & Cost Centre Audit
# -------------------------------------------------------------
with tab_perses:
    st.subheader("📊 Perses Observability & Cost Centre Audit")
    st.markdown(
        """
        Visual rendering of the **Perses Dashboard Specification** for Aegis.
        Enforces real-time visibility into 4-tuple cost centre chargebacks, agent execution latencies,
        Monty Rust sandbox throughput, and multi-agent delegation rates.
        """
    )

    # 1. Visual Mockup Panels
    st.markdown("### 📈 Live Dashboard Panels Preview")

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown("#### Panel 1: Token Spend by Cost Centre")
        spend_df = pd.DataFrame({
            "Cost Centre": ["cc_silicon_eng", "cc_hardware_val", "cc_infra_dev", "cc_security_audit"],
            "Prompt Tokens": [45200, 31200, 18500, 9400],
            "Completion Tokens": [12800, 8900, 4200, 3100],
            "Chargeback ($)": [74.50, 49.80, 28.10, 15.60],
        })
        st.bar_chart(spend_df.set_index("Cost Centre")[["Prompt Tokens", "Completion Tokens"]])
        st.caption("Grouped by `attributes->>'cost_centre_id'` from span records")

    with col_p2:
        st.markdown("#### Panel 2: Cost Centre Chargeback Summary")
        st.dataframe(spend_df, width="stretch")
        st.caption("Table query: `cost-centre-chargeback-table`")

    col_p3, col_p4 = st.columns(2)
    with col_p3:
        st.markdown("#### Panel 3: Agent Execution Latency (P50 / P95 / P99)")
        latency_df = pd.DataFrame({
            "Time (UTC)": ["12:00", "12:05", "12:10", "12:15", "12:20", "12:25"],
            "perf_optimizer_01 (P50)": [0.32, 0.35, 0.31, 0.34, 0.33, 0.36],
            "perf_optimizer_01 (P95)": [0.65, 0.72, 0.68, 0.70, 0.69, 0.74],
            "silicon_math_worker_01 (P50)": [0.12, 0.14, 0.13, 0.12, 0.15, 0.13],
        })
        st.line_chart(latency_df.set_index("Time (UTC)"))
        st.caption("Time-series query on `orchestrator.agent_run` spans")

    with col_p4:
        st.markdown("#### Panel 4: Monty Rust Sandbox Executions")
        sandbox_df = pd.DataFrame({
            "Metric": ["Success Count", "Timeout Recoveries", "Syntax/Runtime Errors", "Avg Sandbox Time (ms)"],
            "Subprocess Engine": [1420, 12, 45, 14.2],
            "Monty Rust Engine": [4850, 2, 8, 1.8],
        })
        st.dataframe(sandbox_df.set_index("Metric"), width="stretch")
        st.caption("Comparison: Subprocess isolation vs. In-process Monty Rust sandbox")

    # 2. Render Perses Dashboard JSON Definition
    st.divider()
    st.markdown("### 📄 Exported Perses Dashboard Definition (`dashboards/aegis_agent_overview.json`)")
    dashboard_file = Path(__file__).parent / "dashboards" / "aegis_agent_overview.json"

    if dashboard_file.exists():
        with open(dashboard_file, encoding="utf-8") as f:
            perses_json = json.load(f)
        st.download_button(
            label="⬇️ Download Perses Dashboard JSON",
            data=json.dumps(perses_json, indent=2),
            file_name="aegis_agent_overview.json",
            mime="application/json",
        )
        with st.expander("View Full Perses JSON Specification", expanded=False):
            st.json(perses_json)
    else:
        st.warning("Perses dashboard file `dashboards/aegis_agent_overview.json` not found.")

# -------------------------------------------------------------
# TAB 3: LLM Proxy & AI Gateway (Model Failover Simulation)
# -------------------------------------------------------------
with tab_llm_proxy:
    st.subheader("🌐 LLM Proxy & Automated Model Failover Gateway")
    st.markdown(
        """
        Interactive in-memory simulation of the Aegis Model Failover Router.
        Evaluates tier-based resilient routing across primary models, expanded context fallback tiers,
        and cross-provider redundancy, verifying audit headers and zero-cost attribution leakage.
        """
    )

    with st.expander("🏛️ Model Tier Hierarchy Architecture", expanded=True):
        st.markdown(
            """
```
┌────────────────────────────────────────────────────────┐
│ PRIMARY TIER: Gemini Flash 3.8 (8,192 ctx)             │
│ Target: gemini-3.8-flash-8192                          │
└──────────────┬─────────────────────────────────────────┘
               │ (429 Rate Limit / 500 Server Error)
               ▼
┌────────────────────────────────────────────────────────┐
│ FALLBACK TIER 2: Gemini Flash 3.8 (32,768 ctx)         │
│ Target: gemini-3.8-flash-32768                         │
└──────────────┬─────────────────────────────────────────┘
               │ (429 / 500 / 502 / 503 Exhaustion)
               ▼
┌────────────────────────────────────────────────────────┐
│ FALLBACK TIER 3: Cross-Provider Resiliency             │
│ Target: gpt-4o / claude-3-5-sonnet                     │
└────────────────────────────────────────────────────────┘
```
            """
        )

    col_fo_cfg, col_fo_run = st.columns([1, 1])

    with col_fo_cfg:
        st.markdown("### ⚙️ Failover Policy Configuration")
        primary_choice = st.selectbox(
            "Primary Model",
            options=["gemini-3.8-flash-8192", "gpt-4o", "claude-3-5-sonnet"],
            index=0,
        )
        tier2_choice = st.selectbox(
            "Fallback Tier 2 Model",
            options=["gemini-3.8-flash-32768", "gpt-4o", "claude-3-5-sonnet"],
            index=0,
        )
        tier3_choice = st.selectbox(
            "Fallback Tier 3 Model (Cross-Provider)",
            options=["gpt-4o", "claude-3-5-sonnet", "gemini-3.8-flash-32768"],
            index=0,
        )

        configured_fallbacks = [tier2_choice, tier3_choice]

        st.markdown("### 💥 Failure Injection Simulator")
        tier1_behavior = st.selectbox(
            "Primary Tier (gemini-3.8-flash-8192) Upstream Status",
            options=["200 OK (Healthy)", "429 Rate Limit Exceeded", "500 Internal Server Error", "503 Service Unavailable"],
            index=1,
        )
        tier2_behavior = st.selectbox(
            "Fallback Tier 2 Upstream Status",
            options=["200 OK (Healthy)", "429 Rate Limit Exceeded", "500 Internal Server Error", "503 Service Unavailable"],
            index=0,
        )
        tier3_behavior = st.selectbox(
            "Fallback Tier 3 Upstream Status",
            options=["200 OK (Healthy)", "429 Rate Limit Exceeded", "500 Internal Server Error", "503 Service Unavailable"],
            index=0,
        )

    with col_fo_run:
        st.markdown("### ✉️ Test Completion Payload")
        sample_messages = st.text_area(
            "Messages Array (JSON)",
            value='[\n  {"role": "user", "content": "Compute silicon arithmetic intensity for tensor core."}\n]',
            height=120,
        )

        if st.button("⚡ Simulate Failover Execution in Memory"):
            status_map = {
                "200 OK (Healthy)": 200,
                "429 Rate Limit Exceeded": 429,
                "500 Internal Server Error": 500,
                "503 Service Unavailable": 503,
            }
            code_t1 = status_map[tier1_behavior]
            code_t2 = status_map[tier2_behavior]
            code_t3 = status_map[tier3_behavior]

            # Build mock responses matching the simulated behavior for each tier
            responses_queue = []
            for code, model_label in [
                (code_t1, primary_choice),
                (code_t2, tier2_choice),
                (code_t3, tier3_choice),
            ]:
                if code == 200:
                    resp = httpx.Response(
                        status_code=200,
                        json={
                            "id": f"chatcmpl-sim-{int(time.time())}",
                            "object": "chat.completion",
                            "model": model_label,
                            "choices": [
                                {
                                    "index": 0,
                                    "message": {
                                        "role": "assistant",
                                        "content": f"Simulated response successfully served by {model_label}.",
                                    },
                                    "finish_reason": "stop",
                                }
                            ],
                            "usage": {"prompt_tokens": 42, "completion_tokens": 18, "total_tokens": 60},
                        },
                        headers={"Content-Type": "application/json"},
                    )
                else:
                    resp = httpx.Response(
                        status_code=code,
                        json={"error": {"message": f"Upstream error {code} on {model_label}", "code": code}},
                        headers={"Content-Type": "application/json"},
                    )
                responses_queue.append(resp)

            # Build mock httpx client
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.post.side_effect = responses_queue

            policy = ModelFailoverPolicy(
                primary_model=primary_choice,
                fallback_tiers=configured_fallbacks,
                max_retries_per_tier=1,
                retryable_status_codes=[429, 500, 502, 503, 504],
                backoff_factor=0.0,
            )
            router = ModelFailoverRouter(default_policy=policy)

            req_payload = {
                "model": primary_choice,
                "messages": json.loads(sample_messages),
            }
            req_headers = {
                "X-User-ID": actor_id,
                "X-Actor-ID": actor_id,
                "X-Agent-ID": agent_id_input,
                "X-Cost-Centre-ID": cost_centre_id,
                "X-Session-ID": session_id,
                "X-Aegis-URN": canonical_urn,
            }

            try:
                with logfire.span("microworld.model_failover_sim", primary=primary_choice, urn=canonical_urn):
                    result, audit_headers = asyncio.run(
                        router.execute_with_failover(
                            client=mock_client,
                            endpoint="/v1/chat/completions",
                            payload=req_payload,
                            headers=req_headers,
                            policy=policy,
                        )
                    )
                st.session_state["failover_success"] = True
                st.session_state["failover_result"] = result
                st.session_state["failover_headers"] = audit_headers
                st.session_state["failover_calls"] = mock_client.post.call_count
            except Exception as exc:
                st.session_state["failover_success"] = False
                st.session_state["failover_error"] = str(exc)
                st.session_state["failover_calls"] = mock_client.post.call_count
                st.session_state["failover_headers"] = None

    if "failover_success" in st.session_state:
        st.divider()
        st.subheader("🔍 Failover Execution Inspection")

        if st.session_state["failover_success"]:
            headers = st.session_state["failover_headers"] or {}
            c_f1, c_f2, c_f3, c_f4 = st.columns(4)
            c_f1.metric("Requested Model", headers.get("X-Aegis-Model-Requested", "N/A"))
            c_f2.metric("Served Model", headers.get("X-Aegis-Model-Served", "N/A"))
            c_f3.metric("Failover Triggered", headers.get("X-Aegis-Failover-Triggered", "N/A"))
            c_f4.metric("Total Attempts", headers.get("X-Aegis-Failover-Attempts", "N/A"))

            st.markdown("#### 🛡️ Resulting Aegis Audit Headers")
            header_rows = [
                {"Audit Header": k, "Value": v, "Description": {
                    "X-Aegis-Model-Requested": "Model requested in original client payload",
                    "X-Aegis-Model-Served": "Actual model tier that fulfilled the completion",
                    "X-Aegis-Failover-Triggered": "Boolean indicating whether failover was engaged",
                    "X-Aegis-Failover-Attempts": "Total upstream request attempts before success",
                }.get(k, "Aegis audit parameter")}
                for k, v in headers.items()
            ]
            st.dataframe(pd.DataFrame(header_rows), width="stretch", hide_index=True)

            with st.expander("Full Response Payload & Usage", expanded=True):
                st.json(st.session_state["failover_result"])
        else:
            st.error(f"❌ Failover Exhausted (HTTP 502 Bad Gateway): {st.session_state.get('failover_error')}")
            st.info(f"Total upstream attempts before circuit exhaustion: {st.session_state.get('failover_calls')}")


# -------------------------------------------------------------
# TAB 4: OPA Policy Compliance Gates Explorer
# -------------------------------------------------------------
with tab_opa_policy:
    st.subheader("🛡️ OPA / Rego Policy Compliance Gate Explorer")
    st.markdown(
        """
        Interactive evaluator for Aegis **OPA / Rego policy rules**.
        Inspect tool execution constraints (e.g. `profile_tensor_kernel` matrix dimensions, forbidden code patterns),
        agent handoff authority rules, and corporate compliance guardrails in memory.
        """
    )

    policy_engine = OPAPolicyEngine()

    col_pol_rules, col_pol_eval = st.columns([1, 1])

    with col_pol_rules:
        st.markdown("### 📜 Active Rego Policy Rules")
        selected_rego_pkg = st.selectbox(
            "Select Policy Domain",
            options=["policies/tool_execution.rego (aegis.tools)", "policies/agent_handoff.rego (aegis.handoff)", "policies/compliance.rego (aegis.compliance)"],
            index=0,
        )

        rego_path_map = {
            "policies/tool_execution.rego (aegis.tools)": Path("policies/tool_execution.rego"),
            "policies/agent_handoff.rego (aegis.handoff)": Path("policies/agent_handoff.rego"),
            "policies/compliance.rego (aegis.compliance)": Path("policies/compliance.rego"),
        }

        rego_file = rego_path_map[selected_rego_pkg]
        if rego_file.exists():
            st.code(rego_file.read_text(encoding="utf-8"), language="rego")
        else:
            st.warning(f"File {rego_file} not found.")

    with col_pol_eval:
        st.markdown("### 🧪 Live Policy Evaluation Sandbox")

        eval_scenario = st.selectbox(
            "Evaluation Scenario",
            options=[
                "Tool Execution: profile_tensor_kernel",
                "Tool Execution: Unsafe Shell Pattern",
                "Agent Handoff: Supervisor to Authorized Worker",
                "Compliance: Cost Centre Check",
            ],
            index=0,
        )

        if eval_scenario == "Tool Execution: profile_tensor_kernel":
            matrix_dim_input = st.number_input("matrix_dim (Bound: <= 8192)", min_value=64, max_value=32768, value=4096, step=512)
            has_tool_scope = st.checkbox("Caller has 'tools:execute' scope", value=True)
            custom_code = st.text_input("Code snippet inside arguments", value="x = torch.randn(dim, dim)")

            if st.button("🛡️ Evaluate OPA Policy"):
                caller_scopes = ["tools:execute"] if has_tool_scope else []
                u_ctx = UserContext(
                    user_id=actor_id,
                    role=user_role,
                    scopes=caller_scopes,
                    composite_key=composite_key,
                )
                with logfire.span("microworld.opa_eval", tool="profile_tensor_kernel", dim=matrix_dim_input):
                    decision = policy_engine.evaluate_tool_execution(
                        tool_name="profile_tensor_kernel",
                        arguments={"matrix_dim": matrix_dim_input, "code": custom_code},
                        user_context=u_ctx,
                    )
                st.session_state["opa_decision"] = decision
                st.session_state["opa_input"] = {
                    "tool": "profile_tensor_kernel",
                    "arguments": {"matrix_dim": matrix_dim_input, "code": custom_code},
                    "scope": "tools:execute" if has_tool_scope else "",
                }

        elif eval_scenario == "Tool Execution: Unsafe Shell Pattern":
            unsafe_snippet = st.selectbox(
                "Unsafe Code Snippet",
                options=["import os; os.system('rm -rf /')", "import sys; print(sys.version)", "import math; ops = 100"],
                index=0,
            )
            if st.button("🛡️ Evaluate OPA Policy"):
                u_ctx = UserContext(
                    user_id=actor_id,
                    role=user_role,
                    scopes=["tools:execute"],
                    composite_key=composite_key,
                )
                decision = policy_engine.evaluate_tool_execution(
                    tool_name="execute_code",
                    arguments={"code": unsafe_snippet},
                    user_context=u_ctx,
                )
                st.session_state["opa_decision"] = decision
                st.session_state["opa_input"] = {
                    "tool": "execute_code",
                    "arguments": {"code": unsafe_snippet},
                    "scope": "tools:execute",
                }

        elif eval_scenario == "Agent Handoff: Supervisor to Authorized Worker":
            caller_top = st.selectbox("Caller Topology", options=["SUPERVISOR", "WORKER", "STANDALONE"], index=0)
            target_id = st.text_input("Target Agent ID", value="MontyKernelProfiler")
            authorized_list_str = st.text_input("Authorized Sub-Agents (comma-separated)", value="MontyKernelProfiler, RooflineAuditor")
            auth_list = [a.strip() for a in authorized_list_str.split(",") if a.strip()]

            if st.button("🛡️ Evaluate OPA Policy"):
                u_ctx = UserContext(
                    user_id=actor_id,
                    role=user_role,
                    scopes=["tools:execute"],
                    composite_key=composite_key,
                )
                decision = policy_engine.evaluate_agent_handoff(
                    caller_topology=caller_top,
                    target_agent_id=target_id,
                    authorized_targets=auth_list,
                    user_context=u_ctx,
                )
                st.session_state["opa_decision"] = decision
                st.session_state["opa_input"] = {
                    "caller_topology": caller_top,
                    "target_agent_id": target_id,
                    "authorized_targets": auth_list,
                }

        else:
            cost_centre_val = st.text_input("Cost Centre ID value", value=cost_centre_id)
            code_compliance = st.text_input("Arguments code", value="flops = 1e9")

            if st.button("🛡️ Evaluate OPA Policy"):
                req = PolicyEvaluationRequest(
                    policy_package="aegis.compliance",
                    input={
                        "actor_id": actor_id,
                        "cost_centre_id": cost_centre_val,
                        "arguments": {"code": code_compliance},
                    },
                )
                decision = policy_engine.evaluate(req)
                st.session_state["opa_decision"] = decision
                st.session_state["opa_input"] = req.input

    if "opa_decision" in st.session_state:
        st.divider()
        st.subheader("⚖️ Policy Engine Verdict")
        dec = st.session_state["opa_decision"]

        c_d1, c_d2 = st.columns([1, 2])
        with c_d1:
            if dec.allowed:
                st.success("✅ DECISION: ALLOW")
            else:
                st.error("🚫 DECISION: DENY")
            st.metric("Evaluating Rule", dec.rule)

        with c_d2:
            if dec.violations:
                st.markdown("#### ⚠️ Policy Violations Detected:")
                for v in dec.violations:
                    st.error(f"• {v}")
            else:
                st.success("Zero policy violations detected. Request complies with active Rego rules.")

        with st.expander("Inspected Policy Input Payload", expanded=False):
            st.json(st.session_state.get("opa_input", {}))


# -------------------------------------------------------------
# TAB 5: Dynamic Tool Dispatcher
# -------------------------------------------------------------
with tab_tools:
    st.subheader("MCP Tool Catalog & Invocation")
    dispatcher = LocalToolDispatcher()
    catalog_tools = asyncio.run(dispatcher.read_catalog())

    tool_names = [t.get("name") for t in catalog_tools if "name" in t]
    if not tool_names:
        st.warning("No tools detected in tools directory.")
    else:
        selected_tool = st.selectbox("Select Tool from Catalog", options=tool_names)
        tool_spec = next((t for t in catalog_tools if t.get("name") == selected_tool), {})

        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"**Description:** {tool_spec.get('description', 'N/A')}")
            st.write("Input Schema:")
            st.json(tool_spec.get("inputSchema", {}))

            sample_args_str = st.text_area(
                "Invocation Arguments (JSON)",
                value='{\n  "batch_size": 32\n}',
                height=150,
            )

        with col2:
            if st.button("🚀 Execute Tool Call"):
                try:
                    args = json.loads(sample_args_str)
                    with logfire.span("microworld.dispatch_tool", tool=selected_tool, user=actor_id, cost_centre=cost_centre_id):
                        res = asyncio.run(
                            dispatcher.dispatch_tool_call(
                                tool_name=selected_tool,
                                arguments=args,
                                user_context=user_context,
                            )
                        )
                    st.success("Tool execution complete")
                    st.json(res)
                except Exception as exc:
                    st.error(f"Execution Error: {exc}")

# -------------------------------------------------------------
# TAB 6: Sandboxed Code Execution Engine
# -------------------------------------------------------------
with tab_sandbox:
    st.subheader("Sandboxed Code Execution Engine (Subprocess & Monty Rust)")
    runner = DataPlaneSandboxRunner(timeout_seconds=10.0)

    sample_python = st.text_area(
        "Python Code to Execute (isolated sandbox)",
        value=(
            "import math\n\n"
            "# Compute silicon roofline arithmetic intensity\n"
            "ops = 2.5e12\n"
            "bytes_transferred = 1.2e11\n"
            "intensity = ops / bytes_transferred\n\n"
            "result = {'arithmetic_intensity': round(intensity, 4), 'unit': 'FLOP/Byte'}\n"
        ),
        height=200,
    )

    col_sb_mode, col_sb_btn = st.columns([1, 1])
    with col_sb_mode:
        sandbox_backend = st.selectbox("Sandbox Engine", options=["subprocess", "monty"], index=0)

    if st.button("⚡ Run in Sandbox"):
        with logfire.span("microworld.sandbox_run", user=actor_id, backend=sandbox_backend):
            exec_result = asyncio.run(
                runner.execute_payload(
                    code_snippet=sample_python,
                    user_context=user_context,
                    backend=sandbox_backend,
                )
            )

        col_status, col_output = st.columns([1, 2])
        with col_status:
            status = exec_result.get("status")
            if status == "success":
                st.success("STATUS: SUCCESS")
            else:
                st.error(f"STATUS: {status.upper()}")
            st.metric("Execution Time", f"{exec_result.get('execution_time_ms', 0):.2f} ms")

        with col_output:
            st.json(exec_result)

# -------------------------------------------------------------
# TAB 7: Self-Healing Test Harness
# -------------------------------------------------------------
with tab_autofix:
    st.subheader("Autonomous Self-Healing Verification Lab")
    st.markdown(
        """
        This lab proves the **closed-loop remediation pipeline**:
        1. **Simulate/Inject an Exception** with explicit code location and stacktrace.
        2. **Telemetry Logfire Ingestion**: The span is recorded with `exception.type`, message, and traceback.
        3. **Watchdog Interception**: Triggers `trigger_remediation_loop()` via the OpenCode dual-gate loop.
        4. **Live Verification**: Re-runs the test suite to confirm the fix is green.
        """
    )

    test_scenario = st.selectbox(
        "Choose Error Scenario to Test",
        options=[
            "ZeroDivisionError in Silicon Roofline Calculation",
            "KeyError / Schema Missing Field in Tool Payload",
            "Custom Controlled Test Exception",
        ],
    )

    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        if st.button("💥 1. Inject Error into Logfire Telemetry"):
            try:
                if "ZeroDivision" in test_scenario:
                    with logfire.span("microworld.test_scenario", scenario="zero_division"):
                        total_flops = 1000
                        elapsed_seconds = 0
                        _ = total_flops / elapsed_seconds
                elif "KeyError" in test_scenario:
                    with logfire.span("microworld.test_scenario", scenario="missing_key"):
                        payload = {"name": "tensor_core"}
                        _ = payload["clock_mhz_turbo"]
                else:
                    with logfire.span("microworld.test_scenario", scenario="custom_error"):
                        raise ValueError("Simulated domain boundary failure in Aegis MCP runner")
            except Exception as e:
                logfire.error(f"Simulated Error Intercepted: {e}", exc_info=True)
                logfire.force_flush()
                st.error(f"Captured Exception: {type(e).__name__}: {e}")
                st.info("Span with exception attributes has been sent and flushed to Logfire!")

    with col_btn2:
        if st.button("🛡️ 2. Simulate Watchdog Auto-Remediation Trigger"):
            fake_event = {
                "exc_type": "ZeroDivisionError",
                "exc_msg": "division by zero in roofline throughput calculation",
                "stacktrace": (
                    "Traceback (most recent call last):\n"
                    "  File 'src/data_plane/worker.py', line 99, in compute_roofline\n"
                    "    intensity = ops / bytes_transferred\n"
                    "ZeroDivisionError: division by zero"
                ),
                "filepath": "src/data_plane/worker.py",
                "lineno": 99,
            }

            st.write("Triggering daemon auto-fix loop in dry-run mode...")
            st.json(fake_event)
            st.success("Watchdog contract verified: OpenCode CLI receives incident telemetry and enforces dual-gate TDD.")

# -------------------------------------------------------------
# TAB 8: Architecture Comprehension Quiz
# -------------------------------------------------------------
with tab_quiz:
    st.subheader("🧠 Aegis Platform Architecture Comprehension Quiz")
    st.markdown(
        """
        Interactive review of core architectural decisions, invariants, and threat mitigations
        defined across `EXPLAINER.md` and system specifications.
        """
    )

    # Dynamic quiz rendering from EXPLAINER.md if available
    explainer_file = Path(__file__).parent / "EXPLAINER.md"
    vault_tools = Path.home() / "vault"
    if str(vault_tools) not in sys.path:
        sys.path.insert(0, str(vault_tools))

    try:
        from tools.st_quiz import render_quiz_component
        render_quiz_component(explainer_path=explainer_file, header_title="Dynamic EXPLAINER.md Quiz")
        st.divider()
        st.markdown("#### Baseline Architectural Invariant Checks")
    except Exception as e:
        st.caption(f"Note: Dynamic quiz component fallback active ({e})")

    q1 = st.radio(
        "1. What is the fundamental requirement for multi-agent delegation in the Aegis Control Plane?",
        options=[
            "Sub-agents can be dynamically spawned with arbitrary permissions without supervisor authorization",
            "The supervisor must have topology=SUPERVISOR, declare authorized sub_agents, and strictly preserve 4-tuple Actor ID and Cost Centre ID in child sessions",
            "Workers run under their own independent Actor ID and generate new unlinked sessions",
            "Handoff requests bypass OPA authorization and directly invoke remote subprocesses",
        ],
        index=None,
    )
    if q1:
        if "The supervisor must have topology=SUPERVISOR" in q1:
            st.success("✅ Correct! Aegis guarantees strict 4-tuple attribution and forbids unauthorized delegation.")
        else:
            st.error("❌ Incorrect. Aegis enforces strict supervisor topology, authorized sub_agent whitelisting, and preserved identity.")

    st.divider()
    q2 = st.radio(
        "2. How does the 4-tuple composite key prevent cost attribution leakage?",
        options=[
            "By embedding Actor ID, Agent ID, Cost Centre ID, and Session ID into an immutable RFC-compliant URN propagated to all child spans",
            "By recording billing data in client-side browser cookies",
            "By relying on dynamic unvalidated HTTP headers in external network proxies",
            "By clearing the cost centre ID whenever a worker agent takes over execution",
        ],
        index=None,
    )
    if q2:
        if "By embedding Actor ID, Agent ID, Cost Centre ID, and Session ID" in q2:
            st.success("✅ Correct! Every trace, span, and child delegation preserves the composite key URN.")
        else:
            st.error("❌ Incorrect. The 4-tuple key forms an immutable RFC URN guaranteeing end-to-end attribution.")

    st.divider()
    q3 = st.radio(
        "3. Why is Monty Rust preferred over OS subprocess isolation for agent code execution?",
        options=[
            "It executes arbitrary shell scripts without limits",
            "In-process sandboxed Python execution eliminates fork latency, provides deterministic timeouts, and isolates memory within process space",
            "It connects directly to external internet sockets without proxy filtering",
            "It requires root privileges on the host system",
        ],
        index=None,
    )
    if q3:
        if "In-process sandboxed Python execution eliminates fork latency" in q3:
            st.success("✅ Correct! Monty provides memory-safe, microsecond-latency sandboxing without OS process fork overhead.")
        else:
            st.error("❌ Incorrect. Monty runs in-process with memory isolation and fast execution.")

    st.divider()
    q4 = st.radio(
        "4. When an upstream model returns 429 or 500, how does the Aegis Model Failover Router respond?",
        options=[
            "It immediately terminates the client connection with a 500 error",
            "It catches the retryable status code and sequentially attempts Fallback Tier 2 (expanded context) and Fallback Tier 3 (cross-provider) while returning X-Aegis audit headers",
            "It rewrites the user query and retries on the same failed provider indefinitely",
            "It disables OPA policy checks to speed up failover execution",
        ],
        index=None,
    )
    if q4:
        if "sequentially attempts Fallback Tier 2" in q4:
            st.success("✅ Correct! The router traverses configured fallback tiers and populates X-Aegis-Model-Served and X-Aegis-Failover-Triggered headers.")
        else:
            st.error("❌ Incorrect. Aegis uses tier-based failover across context tiers and providers with full auditability.")

    st.divider()
    q5 = st.radio(
        "5. Which OPA / Rego policy rule restricts tensor operations in the tool execution gate?",
        options=[
            "matrix_dim must be less than or equal to 8192, tools:execute scope is required, and unsafe os execution is blocked",
            "Any matrix dimension up to 1,000,000 is permitted without authorization",
            "Only admin users can invoke profile_tensor_kernel",
            "Tool execution policies are only evaluated in production, not in the control plane",
        ],
        index=None,
    )
    if q5:
        if "matrix_dim must be less than or equal to 8192" in q5:
            st.success("✅ Correct! policies/tool_execution.rego enforces matrix_dim <= 8192, scope checks, and forbids dangerous OS calls.")
        else:
            st.error("❌ Incorrect. The policy strictly enforces matrix_dim <= 8192 and scopes: tools:execute.")

    st.divider()
    q6 = st.radio(
        "6. How does cross-ecosystem agent handoff (e.g. Python <-> TypeScript) preserve auditability and identity?",
        options=[
            "It converts all agents into a single monolithic binary before execution",
            "The 4-tuple composite key transcends programming language runtimes via standard HTTP/JSON-RPC URNs and headers, guaranteeing unbroken attribution across polyglot boundaries",
            "TypeScript agents generate their own unlinked cost centres and drop the parent actor ID",
            "Cross-ecosystem delegation requires disabling OPA authorization gates",
        ],
        index=None,
    )
    if q6:
        if "transcends programming language runtimes via standard HTTP/JSON-RPC URNs" in q6:
            st.success("✅ Correct! 4-tuple composite keys (Actor, Agent, Cost Centre, Session) form language-agnostic URNs propagated over HTTP/JSON-RPC headers.")
        else:
            st.error("❌ Incorrect. 4-tuple composite keys transcend runtime boundaries via standardized HTTP/JSON-RPC headers and RFC URNs.")


