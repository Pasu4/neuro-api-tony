"""Model module - Keeping track of NeuroAction objects."""

from __future__ import annotations

from typing import Any, NamedTuple


class NeuroAction(NamedTuple):
    """Neuro Action Object."""

    name: str
    description: str
    schema: dict[str, Any] | None


class TonyModel:
    """Tony Model."""

    __slots__ = ("actions", "logs")

    def __init__(self) -> None:
        """Initialize Tony Model."""
        self.actions: list[NeuroAction] = []
        self.logs: dict[str, str] = {}

    def __repr__(self) -> str:
        """Return representation of this model."""
        return f"{self.__class__.__name__}()"

    def add_action(self, action: NeuroAction) -> None:
        """Add an action to the list."""
        self.actions.append(action)

    def remove_action(self, action: NeuroAction) -> None:
        """Remove an action from the list."""
        self.actions.remove(action)

    def remove_action_by_name(self, name: str) -> None:
        """Remove an action from the list by name."""
        # Iterating over tuple copy or else will have
        # error from "list modified during iteration"
        for action in tuple(self.actions):
            if action.name == name:
                self.remove_action(action)

    def clear_actions(self) -> None:
        """Clear all actions from the list."""
        self.actions.clear()

    def has_action(self, name: str) -> bool:
        """Check if an action exists in the list."""
        return any(action.name == name for action in self.actions)

    def get_action_by_name(self, name: str) -> NeuroAction | None:
        """Return an action by name."""
        for action in self.actions:
            if action.name == name:
                return action
        return None

    def add_log(self, tag: str, msg: str) -> None:
        """Add a log message."""
        if tag not in self.logs:
            self.logs[tag] = msg
        else:
            self.logs[tag] += f"\n{msg}"

    def clear_logs(self) -> None:
        """Clear all logs."""
        self.logs.clear()

    def get_logs_formatted(self) -> str:
        """Return formatted log messages."""
        return "\n\n".join(f"--- {tag} ---\n\n{log}" for tag, log in self.logs.items())
