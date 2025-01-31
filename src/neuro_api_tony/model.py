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

    __slots__ = ("actions",)

    def __init__(self) -> None:
        """Initialize Tony Model."""
        self.actions: list[NeuroAction] = []

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
