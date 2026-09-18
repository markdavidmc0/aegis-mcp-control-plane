"""Task-isolated context variables for user identity propagation."""

from contextvars import ContextVar

from src.data_plane.schemas import DataPlaneUserContext

user_context_var: ContextVar[DataPlaneUserContext | None] = ContextVar(
    "user_context_var", default=None
)


def get_current_user_context() -> DataPlaneUserContext | None:
    """Returns the DataPlaneUserContext for the active task context."""
    return user_context_var.get()
