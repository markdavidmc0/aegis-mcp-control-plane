"""Agent specification manifest registry."""

import threading

from src.orchestrator.schemas import AgentSpec


class AgentRegistry:
    """Thread-safe in-memory store for AgentSpec definitions."""

    def __init__(self) -> None:
        """Initialize internal dictionary and re-entrant lock."""
        self._specs: dict[str, AgentSpec] = {}
        self._lock = threading.RLock()

    def register(self, spec: AgentSpec) -> None:
        """Register or overwrite an AgentSpec in the registry."""
        with self._lock:
            self._specs[spec.agent_id] = spec

    def get(self, agent_id: str) -> AgentSpec | None:
        """Retrieve an AgentSpec by its agent_id."""
        with self._lock:
            return self._specs.get(agent_id)

    def list(self) -> list[AgentSpec]:
        """List all registered AgentSpec instances."""
        with self._lock:
            return list(self._specs.values())

    def unregister(self, agent_id: str) -> bool:
        """Unregister an AgentSpec. Returns True if removed, False otherwise."""
        with self._lock:
            if agent_id in self._specs:
                del self._specs[agent_id]
                return True
            return False


# Global singleton registry instance
default_registry = AgentRegistry()
