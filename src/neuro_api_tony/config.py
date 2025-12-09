"""Configuration for Tony."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

import wx
from dataclass_wizard import JSONWizard

# region Enums


class ActionScope(str, Enum):
    """Action scopes."""

    GLOBAL = "global"
    CLIENT = "client"


class ConflictPolicy(str, Enum):
    """Conflict resolution policies for action names."""

    IGNORE = "ignore"
    OVERWRITE = "overwrite"
    ALLOW_DUPLICATES = "allowDuplicates"


class EditorTheme(str, Enum):
    """Editor themes."""

    AUTO = "auto"
    DARK_PLUS = "darkPlus"
    LIGHT_PLUS = "lightPlus"


class EditorThemeColor(str, Enum):
    """Editor color themes."""

    BACKGROUND = "background"
    CARET = "caret"
    COMPACTIRI = "compactIRI"
    DEFAULT = "default"
    KEYWORD = "keyword"
    NUMBER = "number"
    PROPERTYNAME = "propertyName"
    STRING = "string"
    URI = "uri"


class SendActionsTo(str, Enum):
    """Destinations to send actions to."""

    ALL = "all"
    REGISTRANT = "registrant"
    FIRST_CONNECTED = "firstConnected"
    LAST_CONNECTED = "lastConnected"


class WarningID(str, Enum):
    """Warning Identifiers."""

    ACTION_ADDITIONAL_PROPERTIES = "actionAdditionalProperties"
    ACTION_NAME_CONFLICT = "actionNameConflict"
    ACTION_NAME_INVALID = "actionNameInvalid"
    ACTION_SCHEMA_NULL = "actionSchemaNull"
    ACTION_SCHEMA_UNSUPPORTED = "actionSchemaUnsupported"
    ACTIONS_FORCE_INVALID = "actionsForceInvalid"
    EMPTY_UNREGISTER = "emptyUnregister"
    GAME_NAME_MISMATCH = "gameNameMismatch"
    GAME_NAME_NOT_REGISTERED = "gameNameNotRegistered"
    JSF_FAILED = "jsfFailed"
    MULTIPLE_STARTUPS = "multipleStartups"
    NO_ERROR_MESSAGE = "noErrorMessage"
    UNKNOWN_COMMAND = "unknownCommand"


# endregion


# region String aliases


THEMES: Final = {
    EditorTheme.DARK_PLUS: {
        EditorThemeColor.BACKGROUND: "#1E1E1E",
        EditorThemeColor.CARET: "#FFFFFF",
        EditorThemeColor.COMPACTIRI: "#9CDCFE",
        EditorThemeColor.DEFAULT: "#D4D4D4",
        EditorThemeColor.KEYWORD: "#4FC1FF",
        EditorThemeColor.NUMBER: "#B5CEA8",
        EditorThemeColor.PROPERTYNAME: "#9CDCFE",
        EditorThemeColor.STRING: "#CE9178",
        EditorThemeColor.URI: "#CE9178",
    },
    EditorTheme.LIGHT_PLUS: {
        EditorThemeColor.BACKGROUND: "#FFFFFF",
        EditorThemeColor.CARET: "#000000",
        EditorThemeColor.COMPACTIRI: "#9CDCFE",
        EditorThemeColor.DEFAULT: "#000000",
        EditorThemeColor.KEYWORD: "#0000FF",
        EditorThemeColor.NUMBER: "#098658",
        EditorThemeColor.PROPERTYNAME: "#0451A5",
        EditorThemeColor.STRING: "#A31515",
        EditorThemeColor.URI: "#A31515",
    },
}


# endregion


@dataclass
class Config(JSONWizard, key_case="AUTO"):
    """Tony configuration."""

    action_scope: ActionScope = ActionScope.GLOBAL
    allowed_schema_keys: list[str] = field(default_factory=list)
    conflict_policy: ConflictPolicy = ConflictPolicy.IGNORE
    delete_actions_on_disconnect: bool = False
    editor_color_theme: dict[EditorThemeColor, str] | EditorTheme = EditorTheme.AUTO
    log_action_descriptions: bool = True
    log_level: str = "INFO"
    send_actions_to: SendActionsTo = SendActionsTo.REGISTRANT
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


def get_editor_theme_colors() -> Mapping[EditorThemeColor, str]:
    """Get the editor theme colors based on the current configuration."""
    cfg = config().editor_color_theme
    if cfg == EditorTheme.AUTO:
        if wx.SystemSettings.GetAppearance().IsDark():
            return THEMES[EditorTheme.DARK_PLUS]
        return THEMES[EditorTheme.LIGHT_PLUS]
    if isinstance(cfg, EditorTheme):
        return THEMES[cfg]
    return cfg


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
