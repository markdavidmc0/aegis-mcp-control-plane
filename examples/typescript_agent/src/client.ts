/**
 * Aegis HTTP Client attaching the canonical 4-tuple identity headers.
 */

import type {
  AegisIdentityHeaders,
  AgentCompositeKey,
  AgentHandoffRequest,
  AgentRunRequest,
  AgentSessionState,
  AgentSpec,
} from "./types.js";

export class AegisClient {
  private readonly baseUrl: string;
  private readonly compositeKey: AgentCompositeKey;
  private readonly role: string;
  private readonly scopes: string[];

  constructor(options: {
    baseUrl?: string;
    compositeKey: AgentCompositeKey;
    role?: string;
    scopes?: string[];
  }) {
    this.baseUrl = options.baseUrl ?? "http://localhost:8000";
    this.compositeKey = options.compositeKey;
    this.role = options.role ?? "engineer";
    this.scopes = options.scopes ?? ["tools:execute", "llm:proxy"];
  }

  public getHeaders(overrideAgentId?: string, overrideSessionId?: string): Record<string, string> {
    const agentId = overrideAgentId ?? this.compositeKey.agent_id;
    const sessionId = overrideSessionId ?? this.compositeKey.session_id;
    const urn = `urn:aegis:agent:${this.compositeKey.actor_id}:${agentId}:${this.compositeKey.cost_centre_id}:${sessionId}`;

    const headers: AegisIdentityHeaders = {
      "X-Actor-ID": this.compositeKey.actor_id,
      "X-User-ID": this.compositeKey.actor_id,
      "X-Agent-ID": agentId,
      "X-Cost-Centre-ID": this.compositeKey.cost_centre_id,
      "X-Session-ID": sessionId,
      "X-Aegis-URN": urn,
      "X-User-Role": this.role,
      "X-User-Scopes": this.scopes.join(","),
    };

    return { ...headers };
  }

  public async registerSpec(spec: AgentSpec): Promise<AgentSpec> {
    const res = await fetch(`${this.baseUrl}/api/v1/orchestrator/specs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...this.getHeaders(),
      },
      body: JSON.stringify(spec),
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Failed to register spec '${spec.agent_id}': ${res.status} ${errorText}`);
    }

    return (await res.json()) as AgentSpec;
  }

  public async listSpecs(): Promise<AgentSpec[]> {
    const res = await fetch(`${this.baseUrl}/api/v1/orchestrator/specs`, {
      method: "GET",
      headers: { ...this.getHeaders() },
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Failed to list specs: ${res.status} ${errorText}`);
    }

    return (await res.json()) as AgentSpec[];
  }

  public async runAgent(agentId: string, request: AgentRunRequest): Promise<AgentSessionState> {
    const res = await fetch(`${this.baseUrl}/api/v1/orchestrator/runs/${agentId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...this.getHeaders(agentId),
      },
      body: JSON.stringify(request),
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Failed to run agent '${agentId}': ${res.status} ${errorText}`);
    }

    return (await res.json()) as AgentSessionState;
  }

  public async handoff(handoffRequest: AgentHandoffRequest): Promise<AgentSessionState> {
    const res = await fetch(`${this.baseUrl}/api/v1/orchestrator/handoff`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...this.getHeaders(handoffRequest.caller_agent_id, handoffRequest.parent_session_id),
      },
      body: JSON.stringify(handoffRequest),
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Failed handoff from '${handoffRequest.caller_agent_id}' to '${handoffRequest.target_agent_id}': ${res.status} ${errorText}`);
    }

    return (await res.json()) as AgentSessionState;
  }

  public async getSession(sessionId: string): Promise<AgentSessionState> {
    const res = await fetch(`${this.baseUrl}/api/v1/orchestrator/sessions/${sessionId}`, {
      method: "GET",
      headers: { ...this.getHeaders() },
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Failed to get session '${sessionId}': ${res.status} ${errorText}`);
    }

    return (await res.json()) as AgentSessionState;
  }

  public async cancelSession(sessionId: string): Promise<AgentSessionState> {
    const res = await fetch(`${this.baseUrl}/api/v1/orchestrator/sessions/${sessionId}/cancel`, {
      method: "POST",
      headers: { ...this.getHeaders() },
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Failed to cancel session '${sessionId}': ${res.status} ${errorText}`);
    }

    return (await res.json()) as AgentSessionState;
  }
}
