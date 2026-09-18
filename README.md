# Aegis Federated AI MCP Control Plane & Execution Data Plane

Aegis is an enterprise-grade, zero-trust AI Agent execution architecture implementing strict control-plane / data-plane separation, Open Policy Agent (OPA/Rego) compliance gating, automated LLM model failover, and hardware-accelerated sandboxed tool execution.

---

## 1. Architectural Topology & Plane Separation

Aegis strictly decouples operational control and policy validation from untrusted tool evaluation:

```
                                  +---------------------------------------+
                                  | Upstream API Gateway / Envoy Proxy    |
                                  +---------------------------------------+
                                                      |
                                                      |  X-Actor-ID, X-User-ID, X-Cost-Centre-ID,
                                                      |  X-Session-ID, X-User-Scopes, X-Aegis-URN
                                                      v
                                  +---------------------------------------+
                                  |      Aegis Control Plane (FastAPI)    |
                                  |                                       |
                                  |  - Zero-Trust Identity Ingestion      |
                                  |  - OPA/Rego Policy Compliance Engine  |
                                  |  - Automated LLM Tier Failover Router |
                                  |  - Dynamic MCP Tool Catalog & Stubs   |
                                  +---------------------------------------+
                                        /                           \
               LLM Completions         /                             \  mcp: tools/call & tools/list
           (Gemini Flash -> gpt-4o)   /                               \  (Zero-Trust Identity Forwarded)
                                     v                                 v
                +-------------------------+               +-----------------------------------+
                | LiteLLM / Provider Mesh |               |    Aegis Data Plane (FastMCP)     |
                +-------------------------+               |                                   |
                                                          |  - gVisor / In-Memory Isolation   |
                                                          |  - Monty Rust Python REPL Sandbox |
                                                          |  - Hardware SME2 / Tensor Kernels |
                                                          +-----------------------------------+
```

### Decoupled Invariants:
1. **Control Plane (`src/control_plane`)**:
   - Ingests user identity and propagates the canonical **4-tuple composite key**.
   - Evaluates pre-execution compliance policies with **OPA/Rego**.
   - Manages resilient LLM routing with automated tier failover and audit header injection.
   - Generates typed Python stubs from dynamic tool catalogs.
2. **Data Plane (`src/data_plane`)**:
   - Executes untrusted tool calls and scripts inside an isolated runtime.
   - Evaluates AST and bytecodes via the **Monty Rust sandbox** (`pydantic-monty`).
   - Completely air-gapped from direct internet access without control plane mediation.

---

## 2. 4-Tuple Identity & Context Backbone

Every interaction within Aegis is bound to an immutable 4-tuple identity representation:

$$\text{CompositeKey} = \langle \text{actor\_id}, \text{agent\_id}, \text{cost\_centre\_id}, \text{session\_id} \rangle$$

### Canonical Aegis URN
```
urn:aegis:agent:{actor_id}:{agent_id}:{cost_centre_id}:{session_id}
```

- **Strict Schema Invariants**: Implemented in `src/control_plane/schemas.py` and `src/data_plane/schemas.py` with `frozen=True` and `extra="forbid"`.
- **Identity Propagation**: Injected as HTTP headers:
  - `X-Actor-ID`
  - `X-Agent-ID`
  - `X-Cost-Centre-ID`
  - `X-Session-ID`
  - `X-Aegis-URN`
  - `X-User-Scopes`

---

## 3. Automated Model Failover & Tiered Routing

LLM chat completions routed through `/v1/chat/completions` use the `ModelFailoverRouter` (`src/control_plane/failover_router.py`) to guarantee high availability across rate limits and provider outages.

### Failover Tier Hierarchy:
1. **Primary Model**: `gemini-3.8-flash-8192` (Low latency, high throughput)
2. **Fallback Tier 1**: `gemini-3.8-flash-32768` (Expanded context window)
3. **Fallback Tier 2**: `gpt-4o` (High-reasoning generalist fallback)

### Policy Parameters (`ModelFailoverPolicy`):
- `max_retries_per_tier`: 2 (Configurable bounds: 1 to 5)
- `retryable_status_codes`: `[429, 500, 502, 503, 504]`
- `backoff_factor`: `0.5` seconds exponential backoff
- **Audit Headers Injected**:
  - `X-Aegis-Model-Requested`: Requested model identifier
  - `X-Aegis-Model-Served`: Final model providing the completion
  - `X-Aegis-Failover-Triggered`: `"true"` or `"false"`
  - `X-Aegis-Failover-Attempts`: Total attempts made across all tiers
- **Telemetry**: Emits structured Logfire span `llm.model_failover` detailing requested model, served model, attempt counts, and failover status.

---

## 4. OPA / Rego Policy Compliance Engine

Pre-execution safety and agent delegation policies are enforced at the Control Plane boundary via `OPAPolicyEngine` (`src/control_plane/policy_engine.py`):

1. **Tool Execution Compliance (`policies/tool_execution.rego`)**:
   - Scope validation: Caller must hold `tools:execute`.
   - Bounds validation: Matrix dimension (`matrix_dim`) for tensor profiling cannot exceed `8192`.
   - Code security: AST/token scanning blocks unsafe patterns like `import os` or `os.system`.
2. **Agent Handoff Compliance (`policies/agent_handoff.rego`)**:
   - Topology constraints: Only `SUPERVISOR` agents can delegate tasks to other agents.
   - Delegation authorization: Target agent must exist in supervisor's `authorized_targets`.
3. **Gateway Enforcement**:
   - Evaluated during `tools/call` over `/mcp` and `/api/v1/mcp`.
   - Violations return JSON-RPC error `-32000` with explicit denial reasons.

---

## 5. Monty Rust Sandbox & Hardware Kernels

The Data Plane execution engine integrates the **Monty Rust Python Sandbox** (`pydantic-monty`), providing:
- Fast AST verification and bytecode execution without OS-level shell escape risks.
- Kernel execution for Arm SME2 matrix and vector dot operations (`profile_tensor_kernel`).
- Memory allocation limits and compute timeouts.

---

## 6. Polyglot Agent Ecosystem (Python & TypeScript)

Aegis provides first-class contracts and SDKs across multiple runtimes:

- **Python Agents**: `src/control_plane` and `src/data_plane` built with Python 3.12, Pydantic V2, and FastMCP.
- **TypeScript Agents**: `examples/typescript_agent` providing strict interfaces (`AgentSpec`, `AgentSessionState`, `ModelFailoverPolicy`, `PolicyDecision`, `AegisIdentityHeaders`).
- **Interactive Micro-World Harness**: Streamlit UI (`demo_ui.py`) for live simulation of agent handoffs, failover cascades, and policy denials.

---

## 7. Dual Quality Gates & Verification

All code in Aegis satisfies strict automated dual quality gates:

### Python Quality Gate
```bash
# Verifier Gate
uv run pytest

# Linter & Formatting Gate
uv run ruff check src/ tests/ examples/
```

### TypeScript Quality Gate
```bash
# Typecheck Gate
npm --prefix examples/typescript_agent run typecheck
```
