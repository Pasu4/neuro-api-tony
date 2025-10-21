"""Configuration for Tony."""

import json
from dataclasses import dataclass
from typing import Final

from dataclass_wizard import JSONWizard


@dataclass
class Config(JSONWizard, key_case="AUTO"):
    """Tony configuration."""

    conflict_policy: str = "ignoreAlways"
    delete_actions_on_disconnect: bool = True
    log_level: str = "INFO"


_config = Config()


def config() -> Config:
    """Get the global configuration instance."""
    return _config


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
