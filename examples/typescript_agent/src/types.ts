/**
 * Domain contracts and strict types for Aegis TypeScript agents.
 */

export type AgentTopology = "STANDALONE" | "SUPERVISOR" | "WORKER";

export type AgentExecutionStatus =
  | "PENDING"
  | "RUNNING"
  | "PAUSED_AWAITING_HUMAN"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface AgentCompositeKey {
  readonly actor_id: string;
  readonly agent_id: string;
  readonly cost_centre_id: string;
  readonly session_id: string;
}

export interface AgentSpec {
  readonly agent_id: string;
  readonly name: string;
  readonly description: string;
  readonly topology: AgentTopology;
  readonly model?: string;
  readonly system_prompt: string;
  readonly allowed_tools?: string[];
  readonly sub_agents?: string[];
  readonly max_steps?: number;
  readonly timeout_seconds?: number;
}

export interface AgentStepArtifact {
  readonly step_number: number;
  readonly agent_id: string;
  readonly thought?: string;
  readonly tool_call_name?: string | null;
  readonly tool_arguments?: Record<string, unknown> | null;
  readonly tool_output?: unknown | null;
  readonly code_executed?: string | null;
}

export interface AgentSessionState {
  readonly session_id: string;
  readonly composite_key: AgentCompositeKey;
  readonly status: AgentExecutionStatus;
  readonly current_step: number;
  readonly history: AgentStepArtifact[];
  readonly output?: unknown | null;
  readonly error?: string | null;
}

export interface AgentRunRequest {
  readonly prompt: string;
  readonly context?: Record<string, unknown>;
}

export interface AgentHandoffRequest {
  readonly parent_session_id: string;
  readonly caller_agent_id: string;
  readonly target_agent_id: string;
  readonly task_instructions: string;
  readonly context_data?: Record<string, unknown>;
}

export interface AegisIdentityHeaders {
  readonly "X-Actor-ID": string;
  readonly "X-User-ID": string;
  readonly "X-Agent-ID": string;
  readonly "X-Cost-Centre-ID": string;
  readonly "X-Session-ID": string;
  readonly "X-Aegis-URN": string;
  readonly "X-User-Role": string;
  readonly "X-User-Scopes": string;
}

export interface ModelFailoverPolicy {
  readonly primary_model: string;
  readonly fallback_tiers: readonly string[];
  readonly max_retries_per_tier: number;
  readonly retryable_status_codes: readonly number[];
  readonly backoff_factor: number;
}

export interface PolicyDecision {
  readonly allowed: boolean;
  readonly rule: string;
  readonly violations: readonly string[];
}

