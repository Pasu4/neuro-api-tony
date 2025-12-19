"""Configuration for Tony."""

import json
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
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


class LogTheme(str, Enum):
    """Log themes."""

    AUTO = "auto"
    DARK = "dark"
    LIGHT = "light"


class LogThemeColor(str, Enum):
    """Log theme colors."""

    DEFAULT = "default"
    TIMESTAMP = "timestamp"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    CONTEXT_QUERY = "contextQuery"
    CONTEXT_STATE = "contextState"
    CONTEXT_SILENT = "contextSilent"
    CONTEXT_EPHEMERAL = "contextEphemeral"
    CONTEXT_ACTION = "contextAction"
    CONTEXT_ACTION_RESULT_SUCCESS = "contextActionResultSuccess"
    CONTEXT_ACTION_RESULT_FAILURE = "contextActionResultFailure"
    CONTEXT_ORIGIN = "contextOrigin"
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    COMMAND_ADDITION = "commandAddition"


class SendActionsTo(str, Enum):
    """Destinations to send actions to."""

    ALL = "all"
    REGISTRANT = "registrant"
    FIRST_CONNECTED = "firstConnected"
    LAST_CONNECTED = "lastConnected"


class ShowOriginAs(str, Enum):
    """How to show origin of actions, context, etc. in log panels."""

    NONE = "none"
    CLIENT_ID = "clientId"
    GAME_NAME = "gameName"


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


EDITOR_THEMES: Final = {
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


LOG_THEMES: Final = {
    LogTheme.DARK: {
        LogThemeColor.DEFAULT: "#FFFFFF",
        LogThemeColor.TIMESTAMP: "#008000",
        LogThemeColor.DEBUG: "#808080",
        LogThemeColor.INFO: "#80C0FF",
        LogThemeColor.WARNING: "#FFC000",
        LogThemeColor.ERROR: "#FF0000",
        LogThemeColor.CRITICAL: "#C00000",
        LogThemeColor.CONTEXT_QUERY: "#FF00FF",
        LogThemeColor.CONTEXT_STATE: "#80FF80",
        LogThemeColor.CONTEXT_SILENT: "#808080",
        LogThemeColor.CONTEXT_EPHEMERAL: "#80C0FF",
        LogThemeColor.CONTEXT_ACTION: "#0000FF",
        LogThemeColor.CONTEXT_ACTION_RESULT_SUCCESS: "#008000",
        LogThemeColor.CONTEXT_ACTION_RESULT_FAILURE: "#FF0000",
        LogThemeColor.CONTEXT_ORIGIN: "#808080",
        LogThemeColor.INCOMING: "#0000FF",
        LogThemeColor.OUTGOING: "#FF0080",
        LogThemeColor.COMMAND_ADDITION: "#808080",
    },
    LogTheme.LIGHT: {
        LogThemeColor.DEFAULT: "#000000",
        LogThemeColor.TIMESTAMP: "#008000",
        LogThemeColor.DEBUG: "#808080",
        LogThemeColor.INFO: "#80C0FF",
        LogThemeColor.WARNING: "#FFC000",
        LogThemeColor.ERROR: "#FF0000",
        LogThemeColor.CRITICAL: "#C00000",
        LogThemeColor.CONTEXT_QUERY: "#FF00FF",
        LogThemeColor.CONTEXT_STATE: "#80FF80",
        LogThemeColor.CONTEXT_SILENT: "#808080",
        LogThemeColor.CONTEXT_EPHEMERAL: "#80C0FF",
        LogThemeColor.CONTEXT_ACTION: "#0000FF",
        LogThemeColor.CONTEXT_ACTION_RESULT_SUCCESS: "#008000",
        LogThemeColor.CONTEXT_ACTION_RESULT_FAILURE: "#FF0000",
        LogThemeColor.CONTEXT_ORIGIN: "#808080",
        LogThemeColor.INCOMING: "#0000FF",
        LogThemeColor.OUTGOING: "#FF0080",
        LogThemeColor.COMMAND_ADDITION: "#808080",
    },
}


# endregion


# region Cache


_editor_theme_colors: dict[EditorThemeColor, str] | None = None
_log_theme_colors: dict[str, wx.Colour] | None = None


# endregion


@dataclass
class Config(JSONWizard, key_case="AUTO"):
    """Tony configuration."""

    action_scope: ActionScope = ActionScope.GLOBAL
    address: str = "localhost"
    allowed_schema_keys: list[str] = field(default_factory=list)
    conflict_policy: ConflictPolicy = ConflictPolicy.IGNORE
    delete_actions_on_disconnect: bool = False
    editor_color_theme: dict[EditorThemeColor, str] | EditorTheme = EditorTheme.AUTO
    log_action_descriptions: bool = True
    log_color_theme: dict[LogThemeColor, str] | LogTheme = LogTheme.LIGHT
    log_level: str = "INFO"
    port: int = 8000
    send_actions_to: SendActionsTo = SendActionsTo.REGISTRANT
    show_origin_as: ShowOriginAs = ShowOriginAs.NONE
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
_current_config_file: Path | None = None


def config() -> Config:
    """Get the global configuration instance."""
    return _config


def default_config() -> Config:
    """Get a default configuration instance."""
    return _DEFAULT_CONFIG


def load_config_from_file(file_path: str | os.PathLike[str] | None = None) -> None:
    """Load configuration from a JSON file."""
    global _config, _current_config_file
    new_config = Config()
    if file_path is None:
        file_path = _current_config_file
    if file_path is None:
        return
    file_path = Path(file_path).absolute()
    data = json.loads(file_path.read_text(encoding="utf-8"))
    new_config = Config.from_dict(data)
    _config = new_config
    _current_config_file = file_path

    # Invalidate cache
    global _editor_theme_colors
    _editor_theme_colors = None
    global _log_theme_colors
    _log_theme_colors = None


def get_editor_theme_color(key: EditorThemeColor) -> str:
    """Get the editor theme colors based on the current configuration."""
    global _editor_theme_colors
    if _editor_theme_colors is not None:
        return _editor_theme_colors[key]

    # Cache the theme colors
    cfg = config().editor_color_theme
    if cfg == EditorTheme.AUTO:
        if wx.SystemSettings.GetAppearance().IsDark():
            cfg = EDITOR_THEMES[EditorTheme.DARK_PLUS]
        else:
            cfg = EDITOR_THEMES[EditorTheme.LIGHT_PLUS]
    elif isinstance(cfg, EditorTheme):
        cfg = EDITOR_THEMES[cfg]
    _editor_theme_colors = cfg
    return _editor_theme_colors[key]


def get_log_theme_color(key: LogThemeColor) -> wx.Colour:
    """Get the log theme colors based on the current configuration."""
    global _log_theme_colors
    if _log_theme_colors is not None:
        return _log_theme_colors[key]

    # Cache the theme colors
    cfg = config().log_color_theme
    if cfg == LogTheme.AUTO:
        cfg = LOG_THEMES[LogTheme.DARK] if wx.SystemSettings.GetAppearance().IsDark() else LOG_THEMES[LogTheme.LIGHT]
    elif isinstance(cfg, LogTheme):
        cfg = LOG_THEMES[cfg]
    _log_theme_colors = {k: wx.Colour() for k in cfg}
    for k, v in cfg.items():
        _log_theme_colors[k].Set(v)
    return _log_theme_colors[key]


def get_config_file_path() -> Path | None:
    """Get the absolute path to the configuration file if it exists."""
    return _current_config_file


FILE_NAMES: Final = (
    "tony-config.json",
    ".tony-config.json",
    "tony_config.json",
    ".tony_config.json",
    "tony.config.json",
    ".tony.config.json",
    ".tonyrc",
    ".tonyrc.json",
)
"""Possible configuration file names."""

XDG_APPLICATION_FOLDER_NAME: Final = "neuro-api-tony"


def get_user_home_folder() -> Path:
    """Return os-specific home folder path."""
    if sys.platform == "win32" or sys.platform == "cygwin":
        return Path(os.getenv("USERPROFILE", Path.home())).absolute()
    # Non-windows
    # XDG specification says use $HOME environment variable instead of
    # "~"
    return Path(os.getenv("HOME", Path.home())).absolute()  # type: ignore[unreachable,unused-ignore]


def get_system_application_config_folder() -> Path:
    """Return os-specific application configuration folder root path."""
    if sys.platform == "win32" or sys.platform == "cygwin":
        # Windows application configuration folder
        # Get local app data folder
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data is not None:
            return Path(local_app_data).absolute()

        # If not set somehow (shouldn't happen usually), get manually
        return get_user_home_folder() / "AppData" / "Local"

    # Non-windows, get XDG Specification application configuration
    # directory, which is configuration files for applications,
    # including settings and preferences that customize how applications
    # behave
    home = get_user_home_folder()  # type: ignore[unreachable,unused-ignore]
    return Path(os.getenv("XDG_CONFIG_HOME", home / ".config")).absolute()


def get_tony_application_config_folder() -> Path:
    """Return XDG-specification application configuration folder for tony."""
    return get_system_application_config_folder() / XDG_APPLICATION_FOLDER_NAME


def detect_config_file() -> Path | None:
    """Detect if a configuration file exists and return its path."""
    # Current working directory
    cwd = Path.cwd()

    # XDG-specification application configuration folder
    tony_xdg_config = get_tony_application_config_folder()

    # User's home directory
    home = get_user_home_folder()

    for root in (cwd, tony_xdg_config, home):
        for name in FILE_NAMES:
            full_path = root / name
            if full_path.is_file():
                return full_path.absolute()
    return None
