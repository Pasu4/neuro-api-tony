"""Constants - Application global constants."""

from enum import Enum
from typing import Final

APP_NAME: Final = "Tony"
VERSION: Final = "1.6.2"
PACKAGE_NAME: Final = "neuro-api-tony"
GIT_REPO_URL: Final = "https://github.com/Pasu4/neuro-api-tony"
PYPI_URL: Final = "https://pypi.org/project/neuro-api-tony"
PYPI_API_URL: Final = "https://pypi.org/pypi/neuro-api-tony/json"


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
    MULTIPLE_STARTUPS = "multipleStartups"
    NO_ERROR_MESSAGE = "noErrorMessage"
    UNKNOWN_COMMAND = "unknownCommand"
