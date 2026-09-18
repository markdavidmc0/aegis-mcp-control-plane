"""OPA/Rego Policy Compliance Engine for tool execution and agent handoffs."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.control_plane.schemas import PolicyDecision, UserContext


class PolicyEvaluationRequest(BaseModel):
    """Input payload for generic policy evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_package: str
    input: dict[str, Any] = Field(default_factory=dict)


class PolicyEngine:
    """OPA Policy Engine evaluating tool execution and agent delegation rules."""

    def __init__(self, policies_dir: Path | str | None = None) -> None:
        """Initialize PolicyEngine with policy directory."""
        self.policies_dir = Path(policies_dir) if policies_dir else Path("policies")

    def evaluate(self, request: PolicyEvaluationRequest) -> PolicyDecision:
        """Evaluate a raw policy request against known Rego rule definitions."""
        pkg = request.policy_package
        inp = request.input

        if pkg == "aegis.tools":
            return self._evaluate_tools_rego(inp)
        elif pkg == "aegis.handoff":
            return self._evaluate_handoff_rego(inp)
        elif pkg == "aegis.compliance":
            return self._evaluate_compliance_rego(inp)

        return PolicyDecision(
            allowed=False,
            rule=f"{pkg}.unknown",
            violations=[f"Unknown policy package: {pkg}"],
        )

    def _evaluate_tools_rego(self, inp: dict[str, Any]) -> PolicyDecision:
        """Evaluate policies matching policies/tool_execution.rego."""
        scope = inp.get("scope", "")
        tool = inp.get("tool", "")
        arguments = inp.get("arguments", {})
        violations: list[str] = []

        if scope != "tools:execute":
            violations.append("Missing required tools:execute scope")

        if tool == "profile_tensor_kernel":
            matrix_dim = arguments.get("matrix_dim", 0)
            if isinstance(matrix_dim, (int, float)) and matrix_dim > 8192:
                violations.append("arguments_violation: Matrix dimension exceeds maximum permitted bound of 8192")

        code = str(arguments.get("code", ""))
        if "import os" in code or "os.system" in code:
            violations.append("arguments_violation: Unsafe system code execution pattern detected")

        if violations:
            return PolicyDecision(
                allowed=False,
                rule="aegis.tools.allow",
                violations=violations,
            )

        return PolicyDecision(
            allowed=True,
            rule="aegis.tools.allow",
            violations=[],
        )

    def _evaluate_handoff_rego(self, inp: dict[str, Any]) -> PolicyDecision:
        """Evaluate policies matching policies/agent_handoff.rego."""
        caller_topology = inp.get("caller_topology", "")
        target_agent_id = inp.get("target_agent_id", "")
        authorized_targets = inp.get("authorized_targets", [])
        violations: list[str] = []

        if caller_topology != "SUPERVISOR":
            violations.append("Only SUPERVISOR topology agents may execute handoff delegation")

        if target_agent_id not in authorized_targets:
            violations.append(f"Target agent '{target_agent_id}' is not in supervisor authorized sub-agents")

        if violations:
            return PolicyDecision(
                allowed=False,
                rule="aegis.handoff.allow",
                violations=violations,
            )

        return PolicyDecision(
            allowed=True,
            rule="aegis.handoff.allow",
            violations=[],
        )

    def _evaluate_compliance_rego(self, inp: dict[str, Any]) -> PolicyDecision:
        """Evaluate policies matching policies/compliance.rego."""
        actor_id = inp.get("actor_id", "")
        cost_centre_id = inp.get("cost_centre_id", "")
        arguments = inp.get("arguments", {})
        violations: list[str] = []

        if not actor_id:
            violations.append("actor_id is required")
        if not cost_centre_id:
            violations.append("compliance_violation: missing cost_centre_id")

        code = str(arguments.get("code", ""))
        if "import os" in code or "os.system" in code:
            violations.append("compliance_violation: unsafe system code execution")

        if violations:
            return PolicyDecision(
                allowed=False,
                rule="aegis.compliance.allow",
                violations=violations,
            )

        return PolicyDecision(
            allowed=True,
            rule="aegis.compliance.allow",
            violations=[],
        )

    def evaluate_tool_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_context: UserContext,
    ) -> PolicyDecision:
        """Evaluate tool execution safety and scope compliance."""
        scope = "tools:execute" if "tools:execute" in user_context.scopes else ""
        req = PolicyEvaluationRequest(
            policy_package="aegis.tools",
            input={
                "scope": scope,
                "tool": tool_name,
                "arguments": arguments,
            },
        )
        return self.evaluate(req)

    def evaluate_agent_handoff(
        self,
        caller_topology: str,
        target_agent_id: str,
        authorized_targets: list[str],
        user_context: UserContext,
    ) -> PolicyDecision:
        """Evaluate agent handoff delegation permissions."""
        req = PolicyEvaluationRequest(
            policy_package="aegis.handoff",
            input={
                "caller_topology": caller_topology,
                "target_agent_id": target_agent_id,
                "authorized_targets": authorized_targets,
            },
        )
        return self.evaluate(req)


OPAPolicyEngine = PolicyEngine
