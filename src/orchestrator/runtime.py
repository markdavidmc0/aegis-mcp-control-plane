"""Agent runtime orchestration engine."""

import threading
import uuid

import logfire

from src.control_plane.schemas import AgentCompositeKey
from src.orchestrator.registry import AgentRegistry, default_registry
from src.orchestrator.schemas import (
    AgentExecutionStatus,
    AgentHandoffRequest,
    AgentRunRequest,
    AgentSessionState,
    AgentSpec,
    AgentStepArtifact,
    AgentTopology,
)


class AgentRuntimeOrchestrator:
    """Manages multi-agent sessions, execution loops, and hierarchical delegation."""

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        """Initialize runtime with agent registry and in-memory session index."""
        self._registry = registry or default_registry
        self._sessions_by_urn: dict[str, AgentSessionState] = {}
        self._session_id_to_urn: dict[str, str] = {}
        self._lock = threading.RLock()

    @property
    def registry(self) -> AgentRegistry:
        """Return the backing AgentRegistry."""
        return self._registry

    def get_session(self, session_id: str) -> AgentSessionState | None:
        """Retrieve session state by session_id."""
        with self._lock:
            urn = self._session_id_to_urn.get(session_id)
            if not urn:
                return None
            return self._sessions_by_urn.get(urn)

    def cancel_session(self, session_id: str) -> AgentSessionState | None:
        """Cancel an active or pending agent session."""
        with self._lock:
            urn = self._session_id_to_urn.get(session_id)
            if not urn:
                return None
            existing = self._sessions_by_urn.get(urn)
            if not existing:
                return None

            cancelled = AgentSessionState(
                session_id=existing.session_id,
                composite_key=existing.composite_key,
                status=AgentExecutionStatus.CANCELLED,
                current_step=existing.current_step,
                history=existing.history,
                output=existing.output,
                error="Execution cancelled by user or supervisor",
            )
            self._sessions_by_urn[urn] = cancelled
            return cancelled

    async def run(
        self,
        key: AgentCompositeKey,
        request: AgentRunRequest,
    ) -> AgentSessionState:
        """Execute an agent run cycle and record step artifacts."""
        spec = self._registry.get(key.agent_id)
        if not spec:
            raise ValueError(f"Agent '{key.agent_id}' is not registered.")

        with logfire.span(
            "invoke_agent",
            **{
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.name": key.agent_id,
                "gen_ai.system": "openai",
                "gen_ai.request.model": spec.model,
                "actor.id": key.actor_id,
                "agent.id": key.agent_id,
                "cost_centre.id": key.cost_centre_id,
                "session.id": key.session_id,
                "aegis.urn": key.urn,
            },
        ):
            session_state = AgentSessionState(
                session_id=key.session_id,
                composite_key=key,
                status=AgentExecutionStatus.RUNNING,
                current_step=0,
                history=[],
            )
            with self._lock:
                self._sessions_by_urn[key.urn] = session_state
                self._session_id_to_urn[key.session_id] = key.urn

            artifacts = self._execute_agent_steps(spec, request.prompt)

            completed_state = AgentSessionState(
                session_id=key.session_id,
                composite_key=key,
                status=AgentExecutionStatus.COMPLETED,
                current_step=len(artifacts),
                history=artifacts,
                output=f"Successfully processed prompt by {spec.name}",
                error=None,
            )
            with self._lock:
                self._sessions_by_urn[key.urn] = completed_state
            return completed_state

    async def handoff(
        self,
        parent_key: AgentCompositeKey,
        handoff: AgentHandoffRequest,
    ) -> AgentSessionState:
        """Delegate a subtask from a supervisor agent to an authorized worker agent."""
        supervisor_spec = self._registry.get(handoff.caller_agent_id)
        if not supervisor_spec:
            raise ValueError(f"Supervisor agent '{handoff.caller_agent_id}' is not registered.")

        if supervisor_spec.topology != AgentTopology.SUPERVISOR:
            raise ValueError(
                f"Agent '{handoff.caller_agent_id}' is not configured as a SUPERVISOR."
            )

        if handoff.target_agent_id not in supervisor_spec.sub_agents:
            raise ValueError(
                f"Target agent '{handoff.target_agent_id}' is not an authorized sub-agent of '{supervisor_spec.agent_id}'."
            )

        sub_agent_spec = self._registry.get(handoff.target_agent_id)
        if not sub_agent_spec:
            raise ValueError(f"Target sub-agent '{handoff.target_agent_id}' is not registered.")

        child_session_id = f"{parent_key.session_id}-{handoff.target_agent_id}-{uuid.uuid4().hex[:8]}"
        worker_key = AgentCompositeKey(
            actor_id=parent_key.actor_id,
            agent_id=handoff.target_agent_id,
            cost_centre_id=parent_key.cost_centre_id,
            session_id=child_session_id,
        )

        with logfire.span(
            "invoke_agent",
            **{
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.name": handoff.target_agent_id,
                "gen_ai.system": "openai",
                "gen_ai.request.model": sub_agent_spec.model,
                "actor.id": parent_key.actor_id,
                "agent.id": handoff.target_agent_id,
                "cost_centre.id": parent_key.cost_centre_id,
                "session.id": child_session_id,
                "aegis.urn": worker_key.urn,
                "parent_session_id": parent_key.session_id,
                "caller_agent_id": handoff.caller_agent_id,
            },
        ):
            worker_run_req = AgentRunRequest(
                prompt=handoff.task_instructions,
                context=handoff.context_data,
            )
            return await self.run(key=worker_key, request=worker_run_req)

    def _execute_agent_steps(self, spec: AgentSpec, prompt: str) -> list[AgentStepArtifact]:
        """Simulate internal step execution loop with fast in-memory execution."""
        step_1 = AgentStepArtifact(
            step_number=1,
            agent_id=spec.agent_id,
            thought=f"Analyzing received prompt: '{prompt}' under instructions.",
            tool_call_name=spec.allowed_tools[0] if spec.allowed_tools else None,
            tool_arguments={"input": prompt} if spec.allowed_tools else None,
            tool_output="Execution completed successfully" if spec.allowed_tools else None,
        )
        return [step_1]


# Global singleton orchestrator
default_orchestrator = AgentRuntimeOrchestrator()
