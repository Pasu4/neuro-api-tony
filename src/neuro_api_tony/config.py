"""Configuration for Tony."""

import json
from dataclasses import dataclass
from typing import ClassVar, Final

from dataclass_wizard import JSONWizard


@dataclass
class Config(JSONWizard, key_case="AUTO"):
    """Tony configuration."""

    conflict_policy: str = "ignoreAlways"
    delete_actions_on_disconnect: bool = True
    log_level: str = "INFO"

    _instance: ClassVar["Config | None"] = None

    @classmethod
    def instance(cls) -> "Config":
        """Get the global configuration instance."""
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance

    @classmethod
    def load_from_file(cls, file_path: str) -> None:
        """Load configuration from a JSON file."""
        with open(file_path, encoding="utf-8") as f:
            config_data = json.load(f)
        cls._instance = Config.from_dict(config_data)


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
