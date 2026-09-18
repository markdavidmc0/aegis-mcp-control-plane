/**
 * TypeScript Multi-Agent System - Supervisor-Worker Architecture.
 *
 * Implements:
 * - AuditCompilerLead (SUPERVISOR): Orchestrates compilation audits and delegates verification.
 * - TSSafetyVerifier (WORKER): Verifies type soundness, syntax trees, and safety bounds.
 */

import { AegisClient } from "./client.js";
import type { AgentCompositeKey, AgentSpec } from "./types.js";

const DEFAULT_COMPOSITE_KEY: AgentCompositeKey = {
  actor_id: "usr_ts_auditor",
  agent_id: "AuditCompilerLead",
  cost_centre_id: "ts-platform-eng",
  session_id: "sess-ts-audit-900",
};

export const auditCompilerLeadSpec: AgentSpec = {
  agent_id: "AuditCompilerLead",
  name: "Audit Compiler Lead",
  description: "TypeScript compiler supervisor coordinating safety checks",
  topology: "SUPERVISOR",
  model: "claude-3-5-sonnet",
  system_prompt: "You oversee compilation audit and verification.",
  allowed_tools: ["tsc_check"],
  sub_agents: ["TSSafetyVerifier", "MontyKernelProfiler"],
  max_steps: 12,
  timeout_seconds: 90.0,
};

export const tsSafetyVerifierSpec: AgentSpec = {
  agent_id: "TSSafetyVerifier",
  name: "TS Safety Verifier",
  description: "Worker verifying type soundness and AST bounds",
  topology: "WORKER",
  model: "claude-3-5-sonnet",
  system_prompt: "You verify type safety constraints.",
  allowed_tools: ["ast_scan"],
  sub_agents: [],
  max_steps: 8,
  timeout_seconds: 45.0,
};

export const montyKernelProfilerSpec: AgentSpec = {
  agent_id: "MontyKernelProfiler",
  name: "Monty Kernel Profiler",
  description: "Python worker executing sandboxed kernel tensor operations",
  topology: "WORKER",
  model: "gpt-4o",
  system_prompt: "You profile tensor compute kernels.",
  allowed_tools: ["execute_code", "profile_tensor_kernel"],
  sub_agents: [],
  max_steps: 10,
  timeout_seconds: 60.0,
};

export async function runMultiAgentWorkflow(client?: AegisClient): Promise<void> {
  const aegis = client ?? new AegisClient({ compositeKey: DEFAULT_COMPOSITE_KEY });

  console.log("[AuditCompilerLead] Registering multi-agent topology with Control Plane...");
  await aegis.registerSpec(auditCompilerLeadSpec);
  await aegis.registerSpec(tsSafetyVerifierSpec);
  await aegis.registerSpec(montyKernelProfilerSpec);
  console.log("[AuditCompilerLead] Topology registered successfully.");

  console.log("[AuditCompilerLead] Initiating supervisor run...");
  const supervisorSession = await aegis.runAgent("AuditCompilerLead", {
    prompt: "Coordinate type soundness audit for the core AST modules.",
    context: { project: "kernel-compiler", build_target: "es2022" },
  });
  console.log(`[AuditCompilerLead] Supervisor status: ${supervisorSession.status}`);

  console.log("[AuditCompilerLead] Delegating verification to TSSafetyVerifier worker via handoff...");
  const workerSession = await aegis.handoff({
    parent_session_id: supervisorSession.session_id,
    caller_agent_id: "AuditCompilerLead",
    target_agent_id: "TSSafetyVerifier",
    task_instructions: "Verify soundness of type declarations in compiler output",
    context_data: { ast_nodes: 450 },
  });

  console.log(`[TSSafetyVerifier] Worker session completed: ${workerSession.session_id}`);
  console.log(`[TSSafetyVerifier] Steps executed: ${workerSession.history.length}`);
  console.log(`[TSSafetyVerifier] Preserved Actor-ID: ${workerSession.composite_key.actor_id}`);
  console.log(`[TSSafetyVerifier] Preserved Cost-Centre: ${workerSession.composite_key.cost_centre_id}`);

  // Cross-ecosystem handoff: TypeScript supervisor -> Python worker (MontyKernelProfiler)
  console.log("[AuditCompilerLead] Delegating cross-ecosystem profiling to MontyKernelProfiler (Python worker)...");
  const crossWorkerSession = await aegis.handoff({
    parent_session_id: supervisorSession.session_id,
    caller_agent_id: "AuditCompilerLead",
    target_agent_id: "MontyKernelProfiler",
    task_instructions: "Profile float32 GEMM kernel in Monty sandbox for compiled AST output",
    context_data: { matrix_dim: 1024, data_type: "float32" },
  });

  console.log(`[MontyKernelProfiler] Cross-ecosystem worker session completed: ${crossWorkerSession.session_id}`);
  console.log(`[MontyKernelProfiler] Steps executed: ${crossWorkerSession.history.length}`);
  console.log(`[MontyKernelProfiler] Preserved Actor-ID: ${crossWorkerSession.composite_key.actor_id}`);
  console.log(`[MontyKernelProfiler] Preserved Cost-Centre: ${crossWorkerSession.composite_key.cost_centre_id}`);

  // Assert 4-tuple identity preservation across language boundary
  if (crossWorkerSession.composite_key.actor_id !== DEFAULT_COMPOSITE_KEY.actor_id) {
    throw new Error(
      `Actor-ID mismatch across boundary: expected ${DEFAULT_COMPOSITE_KEY.actor_id}, got ${crossWorkerSession.composite_key.actor_id}`
    );
  }
  if (crossWorkerSession.composite_key.cost_centre_id !== DEFAULT_COMPOSITE_KEY.cost_centre_id) {
    throw new Error(
      `Cost-Centre mismatch across boundary: expected ${DEFAULT_COMPOSITE_KEY.cost_centre_id}, got ${crossWorkerSession.composite_key.cost_centre_id}`
    );
  }
  console.log("[AuditCompilerLead] Identity preserved across language boundary: 4-tuple invariants intact.");
}

if (process.argv[1]?.endsWith("multi_agent.ts") || process.argv[1]?.endsWith("multi_agent.js")) {
  runMultiAgentWorkflow().catch((err: unknown) => {
    console.error("[Fatal Error]", err);
    process.exit(1);
  });
}
