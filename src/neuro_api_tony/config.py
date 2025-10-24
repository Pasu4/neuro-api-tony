"""Configuration for Tony."""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

from dataclass_wizard import JSONWizard

from .constants import WarningID

# region Enums


class ActionScope(str, Enum):
    """Action scopes."""

    GLOBAL = "global"
    GAME = "game"


class ConflictPolicy(str, Enum):
    """Conflict resolution policies for action names."""

    IGNORE = "ignore"
    OVERWRITE = "overwrite"
    ALLOW_DUPLICATES = "allowDuplicates"


# endregion


@dataclass
class Config(JSONWizard, key_case="AUTO"):
    """Tony configuration."""

    action_scope: ActionScope = ActionScope.GAME
    allowed_schema_keys: list[str] = field(default_factory=list)
    conflict_policy: ConflictPolicy = ConflictPolicy.IGNORE
    delete_actions_on_disconnect: bool = False
    log_action_descriptions: bool = True
    log_level: str = "INFO"
    warnings: dict[WarningID, bool] = field(
        default_factory=lambda: {
            WarningID.ACTION_ADDITIONAL_PROPERTIES: True,
            WarningID.ACTION_NAME_CONFLICT: True,
            WarningID.ACTION_NAME_INVALID: True,
            WarningID.ACTION_SCHEMA_NULL: True,
            WarningID.ACTION_SCHEMA_UNSUPPORTED: True,
            WarningID.ACTIONS_FORCE_INVALID: True,
            WarningID.EMPTY_UNREGISTER: True,
            WarningID.GAME_NAME_MISMATCH: True,
            WarningID.GAME_NAME_NOT_REGISTERED: True,
            WarningID.MULTIPLE_STARTUPS: True,
            WarningID.NO_ERROR_MESSAGE: True,
            WarningID.UNKNOWN_COMMAND: True,
        },
    )


_config = Config()
_DEFAULT_CONFIG: Final = Config()


def config() -> Config:
    """Get the global configuration instance."""
    return _config


def default_config() -> Config:
    """Get a default configuration instance."""
    return _DEFAULT_CONFIG


def load_config_from_file(file_path: str) -> None:
    """Load configuration from a JSON file."""
    global _config
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    _config = Config.from_dict(data)


FILE_NAMES: Final = [
    "tony-config.json",
    ".tony-config.json",
    "tony_config.json",
    ".tony_config.json",
    "tony.config.json",
    ".tony.config.json",
    ".tonyrc",
    ".tonyrc.json",
]
"""Possible configuration file names."""
