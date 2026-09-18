# Control Plane Client Agent Examples

This directory contains reference implementations of AI agents interacting with the Aegis Control Plane gateway via Code Mode REPL execution, MCP JSON-RPC tool dispatching, and multi-agent supervisor-worker delegation hierarchies.

---

## 1. Directory Structure

```
examples/
├── README.md                      # This guide
├── demo_polyglot_codesign.py      # Master driver: Bidirectional Python ⇄ TypeScript co-design
├── python_agent/                  # Python agent implementations
│   ├── agent.py                   # Standalone agent with Code Mode & catalog discovery
│   ├── multi_agent_system.py      # SiliconBenchmarkLead supervisor + worker hierarchy
│   ├── demo_failover.py           # Runnable demo: model failover & audit header inspection
│   └── demo_policy_gate.py        # Runnable demo: OPA / Rego policy enforcement
├── typescript_agent/              # TypeScript Node.js agent implementations
│   ├── package.json               # Scripts (start, typecheck) & dependencies
│   ├── tsconfig.json              # Strict TS configuration (ES2022, NodeNext)
│   └── src/
│       ├── types.ts               # Domain types (4-tuple identity, specs, handoff)
│       ├── client.ts              # AegisClient HTTP client with 4-tuple headers
│       └── multi_agent.ts         # AuditCompilerLead supervisor + TSSafetyVerifier worker
└── tools/                         # MCP Catalog tool sources and schemas
    ├── catalog.json               # Tool definitions (get_accelerator_specs, etc.)
    └── src/                       # Tool python scripts
```

---

## 2. Prerequisites & Platform Deployment

You can run the platform stack either via **Docker Compose** (recommended for production-like multi-container environments) or **Direct Local ASGI** (fastest for development).

### Option A: Docker Compose Deployment (Multi-Container)

Ensure Docker and the Docker Compose plugin are running:

```bash
# 1. Build and launch all stack services in the background
docker compose up -d --build

# 2. Verify containers are healthy
docker compose ps
```

Expected output:
```
NAME                 IMAGE                         STATUS                    PORTS
arm-control-plane    aegis-mcp-control-plane...   Up (healthy)              0.0.0.0:8000->8000/tcp
arm-data-plane       aegis-mcp-control-plane...   Up (healthy)              0.0.0.0:8001->8001/tcp
```

Verify service reachability:
```bash
# Control Plane health check
curl -s http://localhost:8000/health | jq .
# Expected: {"status": "healthy"}

# Data Plane health check
curl -s http://localhost:8001/health | jq .
# Expected: {"status": "healthy"}
```

To view real-time logs or tear down:
```bash
# View combined logs
docker compose logs -f

# Teardown containers and networks
docker compose down
```

---

### Option B: Local ASGI Development Servers

If Docker is not running on your host, launch both microservices in separate terminal windows using `uv`:

```bash
# Terminal 1: Launch Data Plane sandbox worker (port 8001)
uv run uvicorn src.data_plane.mcp_server:app --port 8001

# Terminal 2: Launch Control Plane gateway (port 8000)
DATA_PLANE_URL=http://localhost:8001 uv run uvicorn src.control_plane.main:app --port 8000
```

---

## 3. Python Agent Walkthrough

The Python examples showcase two interaction patterns with the Aegis platform.

### A. Standalone Agent with Code Mode (`examples/python_agent/agent.py`)

A Pydantic AI agent configured with `CodeMode(tools="all")` that interacts with the Control Plane over `/api/v1/mcp` and `/v1/chat/completions`.

#### Key Highlights:
- Attaches the 4-tuple identity headers (`X-Actor-ID`, `X-User-ID`, `X-Cost-Centre-ID`, `X-Session-ID`).
- Calls `discover_catalog_tools` to dynamically query available MCP tools (`tools/list`).
- Invokes `execute_code_in_sandbox` to benchmark tensor kernels inside the Monty Rust execution sandbox.

#### Running the Standalone Agent:
```bash
uv run python examples/python_agent/agent.py
```

#### Expected Output:
```
[Vortex Agent] Starting Workflow via Control Plane Gateway...
Prompt:
1. Discover available tools using `discover_catalog_tools`.
2. Fetch specs for 'vortex-npu-v2'.
3. Benchmark float32 GEMM kernels across matrix dimensions [256, 1024, 2048].
4. Calculate which dimensions operate above vs below the hardware ridge point.

[Vortex Agent] Roofline Optimization Report:
- Accelerator: vortex-npu-v2 (Peak FLOPS: 128 TFLOPS, Memory Bandwidth: 33.2 GB/s)
- Ridge Point: 3.86 FLOPs/byte
- Benchmarks:
  * Dim 256:  Intensity 0.98 FLOPs/byte -> Memory-Bound (below ridge point)
  * Dim 1024: Intensity 3.92 FLOPs/byte -> Compute-Bound (above ridge point)
  * Dim 2048: Intensity 4.12 FLOPs/byte -> Compute-Bound (above ridge point)
```

---

### B. Hierarchical Multi-Agent System (`examples/python_agent/multi_agent_system.py`)

Demonstrates enterprise supervisor-to-worker task delegation using the Aegis Orchestrator Handoff protocol (`POST /api/v1/orchestrator/handoff`).

#### Architecture:
- 👑 **`SiliconBenchmarkLead` (SUPERVISOR):** Formulates the benchmarking matrix and delegates sub-tasks.
- 🛠️ **`MontyKernelProfiler` (WORKER):** Profiles tensor compute kernels using sandboxed code execution in the Monty Rust engine.
- 🛠️ **`RooflineAuditor` (WORKER):** Evaluates arithmetic intensity against accelerator specs (`vortex-npu-v2`) and verifies ridge points.

#### Running the Multi-Agent System:
```bash
uv run python examples/python_agent/multi_agent_system.py
```

#### Expected Execution Walkthrough:
1. **Spec Registration:** Supervisor and worker specs are registered with `/api/v1/orchestrator/specs`.
2. **Supervisor Invocation:** A run is initiated for `SiliconBenchmarkLead` under session `sess-benchmark-flow-001`.
3. **Delegation Handoff 1:** Supervisor invokes `POST /api/v1/orchestrator/handoff` delegating kernel profiling to `MontyKernelProfiler`. The worker executes code in the Monty sandbox and returns step artifacts.
4. **Delegation Handoff 2:** Supervisor delegates hardware limit auditing to `RooflineAuditor`.
5. **4-Tuple Key Preservation:** Notice that `actor_id` (`usr_vortex_lead`) and `cost_centre_id` (`silicon-perf-lab`) are preserved across all child spans, while `session_id` branches hierarchically (`sess-benchmark-flow-001-MontyKernelProfiler-...`).

---

## 4. TypeScript Agent Walkthrough

The TypeScript agent (`examples/typescript_agent/`) demonstrates client integration from Node.js (v20+) or Bun with complete type safety and identity propagation.

### A. Architecture

- 👑 **`AuditCompilerLead` (SUPERVISOR):** Coordinates compilation audits and oversees safety bounds.
- 🛠️ **`TSSafetyVerifier` (WORKER):** Verifies type soundness, AST tree node counts, and static invariant constraints.

### B. Setup & Execution

Navigate to the TypeScript agent directory:
```bash
cd examples/typescript_agent
```

Install dependencies (if not already installed):
```bash
npm install
```

#### Type-Check Quality Gate:
```bash
npm run typecheck
```
Expected output:
```
> aegis-typescript-agent@0.1.0 typecheck
> tsc --noEmit
(Exit code 0, 0 diagnostic errors)
```

#### Run the Multi-Agent Workflow:
```bash
npm run start
```
*Note: You can also execute with `npx tsx src/multi_agent.ts`.*

#### Expected Output:
```
[AuditCompilerLead] Registering multi-agent topology with Control Plane...
[AuditCompilerLead] Topology registered successfully.
[AuditCompilerLead] Initiating supervisor run...
[AuditCompilerLead] Supervisor status: COMPLETED
[AuditCompilerLead] Delegating verification to TSSafetyVerifier worker via handoff...
[TSSafetyVerifier] Worker session completed: sess-ts-audit-900-TSSafetyVerifier-a1b2c3d4
[TSSafetyVerifier] Steps executed: 1
[TSSafetyVerifier] Preserved Actor-ID: usr_ts_auditor
[TSSafetyVerifier] Preserved Cost-Centre: ts-platform-eng
```

---

## 5. Bidirectional Cross-Ecosystem Collaboration (Python ⇄ TypeScript)

The Aegis Control Plane orchestrates agent topologies across language boundaries without losing 4-tuple identity (`actor_id`, `agent_id`, `cost_centre_id`, `session_id`).

### A. Co-Design Pipeline Architecture

The co-design pipeline brings together hardware silicon benchmarking (Python) and compiler AST verification (TypeScript):

1. **Topologies Registered:**
   - 👑 `SiliconBenchmarkLead` (Python Supervisor, `silicon-perf-lab` cost centre)
   - 🛠️ `MontyKernelProfiler` (Python Worker, Monty sandbox execution)
   - 🛠️ `RooflineAuditor` (Python Worker, accelerator specs & ridge points)
   - 👑 `AuditCompilerLead` (TypeScript Supervisor, `ts-platform-eng` cost centre)
   - 🛠️ `TSSafetyVerifier` (TypeScript Worker, type soundness & AST bounds)

2. **Bidirectional Co-Design Flow:**
   - **Phase 1 (Python ➔ Python):** `SiliconBenchmarkLead` delegates tensor kernel profiling to `MontyKernelProfiler` for a 2048x2048 float32 GEMM.
   - **Phase 2 (Python ➔ TypeScript Cross-Handoff):** `SiliconBenchmarkLead` cross-delegates to `TSSafetyVerifier` to verify AST memory constraints and bound checks for matrix dimension 2048.
   - **Phase 3 (Python ➔ Python):** `SiliconBenchmarkLead` delegates to `RooflineAuditor` to evaluate operational intensity against hardware limits.
   - **Phase 4 (TypeScript ➔ Python Cross-Handoff):** `AuditCompilerLead` cross-delegates to `MontyKernelProfiler` to benchmark JIT compiler kernel code directly in the Monty sandbox.

3. **Invariants Preserved:**
   - **4-Tuple Lineage Preservation:** Child sessions preserve `actor_id` and `cost_centre_id` from their respective supervisor callers, preventing cost leakage across ecosystem boundaries.
   - **Hierarchical Session Branching:** Child session IDs branch predictably (e.g., `sess-benchmark-flow-001-TSSafetyVerifier-<uuid>`).

### B. Running the Polyglot Co-Design Demonstration

```bash
uv run python examples/demo_polyglot_codesign.py
```

#### Sample Execution Output:
```text
==============================================================================
AEGIS CONTROL PLANE: BIDIRECTIONAL POLYGLOT CO-DESIGN DEMONSTRATION
==============================================================================
[Topology] Registering 5 polyglot agent specifications with Control Plane...
  + Registered: SiliconBenchmarkLead (SUPERVISOR)
  + Registered: MontyKernelProfiler (WORKER)
  + Registered: RooflineAuditor (WORKER)
  + Registered: AuditCompilerLead (SUPERVISOR)
  + Registered: TSSafetyVerifier (WORKER)

------------------------------------------------------------------------------
PHASE 1: Python Supervisor -> Python Worker (Intra-Ecosystem)
Delegating tensor kernel profiling to MontyKernelProfiler...
  * Status: COMPLETED
  * Child Session ID: sess-benchmark-flow-001-MontyKernelProfiler-2ef64d7c
  * Preserved Actor: usr_vortex_lead
  * Preserved Cost-Centre: silicon-perf-lab

------------------------------------------------------------------------------
PHASE 2: Python Supervisor -> TypeScript Worker (Cross-Ecosystem)
Delegating AST memory constraints verification to TSSafetyVerifier...
  * Status: COMPLETED
  * Child Session ID: sess-benchmark-flow-001-TSSafetyVerifier-1c9ab48a
  * Preserved Actor: usr_vortex_lead
  * Preserved Cost-Centre: silicon-perf-lab

------------------------------------------------------------------------------
PHASE 3: Python Supervisor -> Python Worker (Intra-Ecosystem)
Delegating hardware roofline and ridge point auditing to RooflineAuditor...
  * Status: COMPLETED
  * Child Session ID: sess-benchmark-flow-001-RooflineAuditor-7b3d2ef9
  * Preserved Actor: usr_vortex_lead
  * Preserved Cost-Centre: silicon-perf-lab

------------------------------------------------------------------------------
PHASE 4: TypeScript Supervisor -> Python Worker (Cross-Ecosystem)
Delegating JIT kernel profiling to MontyKernelProfiler from TypeScript Lead...
  * Status: COMPLETED
  * Child Session ID: sess-ts-audit-900-MontyKernelProfiler-5a1e2f80
  * Preserved Actor: usr_ts_auditor
  * Preserved Cost-Centre: ts-platform-eng

==============================================================================
CO-DESIGN EXECUTION & AUDIT SUMMARY
==============================================================================
Phase    | Supervisor (Ecosystem)     | Worker (Ecosystem)       | Preserved Cost-Centre | Status
--------------------------------------------------------------------------------------------
Phase 1  | SiliconBenchmarkLead (PY)  | MontyKernelProfiler (PY) | silicon-perf-lab   | COMPLETED
Phase 2  | SiliconBenchmarkLead (PY)  | TSSafetyVerifier (TS)    | silicon-perf-lab   | COMPLETED
Phase 3  | SiliconBenchmarkLead (PY)  | RooflineAuditor (PY)     | silicon-perf-lab   | COMPLETED
Phase 4  | AuditCompilerLead (TS)     | MontyKernelProfiler (PY) | ts-platform-eng    | COMPLETED
--------------------------------------------------------------------------------------------
4-Tuple Lineage Preservation: 100% INTACT (Zero Cost Centre Leakage Across Boundaries)
==============================================================================
```

---

## 6. Automated Model Failover in Action

The Control Plane gateway includes automated multi-tier / multi-provider failover for all `/v1/chat/completions` traffic:
- **Tier 1 (Primary):** `gemini-3.8-flash-8192` (8k context window, low latency).
- **Tier 2 (Fallback):** `gemini-3.8-flash-32768` (32k context window, triggered upon 429 rate limit or capacity exhaustion).
- **Tier 3 (Cross-Provider Resiliency):** `gpt-4o` / `claude-3-5-sonnet`.

When failover triggers, the gateway automatically injects audit headers into the response:
- `X-Aegis-Model-Requested`: The model requested by the client.
- `X-Aegis-Model-Served`: The fallback model that fulfilled the request.
- `X-Aegis-Failover-Triggered`: `true` or `false`.
- `X-Aegis-Failover-Attempts`: Total attempts made across tiers.

### Running the Model Failover Demonstration

A dedicated runnable client script is provided in `examples/python_agent/demo_failover.py`:

```bash
uv run python examples/python_agent/demo_failover.py
```

#### Expected Output:
```text
======================================================================
AEGIS CONTROL PLANE: AUTOMATED MODEL FAILOVER DEMO
======================================================================

[Step 1] Requesting Primary Tier: gemini-3.8-flash-8192...
Status Code: 200
Audit Response Headers:
  x-aegis-model-requested: gemini-3.8-flash-8192
  x-aegis-model-served: gemini-3.8-flash-8192
  x-aegis-failover-triggered: false
  x-aegis-failover-attempts: 1

[Step 2] Failover Tier Architecture:
  - Tier 1: gemini-3.8-flash-8192  (8,192 context window, cost/latency optimal)
  - Tier 2: gemini-3.8-flash-32768 (32,768 context window, failover target)
  - Tier 3: gpt-4o                 (Cross-provider resiliency fallback)

Note: When Tier 1 encounters HTTP 429 (Rate Limit) or 500/502/503/504 errors,
the gateway seamlessly switches to Tier 2 without client interruption.
```

You can also simulate and inspect model failovers interactively in the Streamlit micro-world (`streamlit run demo_ui.py` -> **Tab 3: LLM Proxy & AI Gateway**).

---

## 7. OPA / Rego Policy Compliance Gating

All tool calls (`/api/v1/mcp`) and agent handoffs (`/api/v1/orchestrator/handoff`) pass through the declarative Open Policy Agent (OPA) compliance engine (`policies/`):

- **Tool Call Bounds (`policies/tool_execution.rego`):** Rejects `profile_tensor_kernel` calls when `matrix_dim > 8192`.
- **Sandbox Security (`policies/compliance.rego`):** Blocks unsafe code patterns (e.g. `import os; os.system`).
- **Delegation Bounds (`policies/agent_handoff.rego`):** Requires caller topology to be `SUPERVISOR` and restricts targets to declared `sub_agents`.

If a policy rule is violated, the gateway returns an immediate `403 Forbidden` or JSON-RPC error code `-32000` detailing the exact policy violation without invoking backend workers.

### Running the OPA Policy Compliance Demonstration

A dedicated runnable client script is provided in `examples/python_agent/demo_policy_gate.py`:

```bash
uv run python examples/python_agent/demo_policy_gate.py
```

#### Expected Output:
```text
======================================================================
AEGIS CONTROL PLANE: OPA / REGO POLICY COMPLIANCE GATE DEMO
======================================================================

[Test 1] Valid Tool Call: profile_tensor_kernel with matrix_dim=2048 (<= 8192)
Result: ALLOWED by OPA Policy.
Data Plane Output: {'device': 'vortex-npu-v2', 'matrix_dim': 2048, 'status': 'success'}

----------------------------------------------------------------------
[Test 2] Policy Violation: profile_tensor_kernel with matrix_dim=16384 (> 8192)
Expected: OPA Rego rule blocks call and returns JSON-RPC error -32000.
Result: DENIED by OPA Policy (Code: -32000)
Error Message: Policy evaluation denied: arguments_violation: Matrix dimension exceeds maximum permitted bound of 8192

----------------------------------------------------------------------
[Test 3] Security Violation: execute_code with unsafe system operation
Expected: OPA Rego rule blocks code with unsafe patterns.
Result: DENIED by OPA Policy (Code: -32000)
Error Message: Policy evaluation denied: arguments_violation: Unsafe system code execution pattern detected
```

---

## 8. Dual Quality Gate Verification

To ensure full compliance with the repository invariants defined in `AGENTS.md`:

```bash
# 1. Run full test suite (159+ passing tests)
uv run pytest

# 2. Run Python linter & static analysis gate
uv run ruff check src/ tests/ examples/ demo_ui.py

# 3. Run TypeScript typecheck gate
npm --prefix examples/typescript_agent run typecheck
```
