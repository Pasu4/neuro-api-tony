"""Model module - Keeping track of NeuroAction objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from neuro_api.json_schema_types import SchemaObject


class NeuroAction(NamedTuple):
    """Neuro Action Object."""

    name: str
    description: str
    schema: SchemaObject | None
    client_id: int
    game: str


class TonyModel:
    """Tony Model."""

    __slots__ = ("actions", "last_action_data", "logs")

    def __init__(self) -> None:
        """Initialize Tony Model."""
        self.actions: list[NeuroAction] = []
        self.logs: dict[str, str] = {}
        self.last_action_data: dict[str, str] = {}

    def __repr__(self) -> str:
        """Return representation of this model."""
        return f"{self.__class__.__name__}()"

    def add_action(self, action: NeuroAction) -> None:
        """Add an action to the list."""
        self.actions.append(action)

    def _remove_action(self, action: NeuroAction) -> None:
        """Remove an action from the list."""
        self.actions.remove(action)

    def remove_actions(self, name: str | None = None, client_id: int | None = None, game: str | None = None) -> None:
        """Remove actions from the list by name and/or client_id."""
        for action in tuple(self.actions):
            name_match = name is None or action.name == name
            client_id_match = client_id is None or action.client_id == client_id
            game_match = game is None or action.game == game
            if name_match and client_id_match and game_match:
                self._remove_action(action)

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
