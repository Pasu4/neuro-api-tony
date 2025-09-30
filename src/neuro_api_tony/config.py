"""Configuration for Tony."""

from dataclasses import dataclass

from dataclass_wizard import JSONWizard


@dataclass
class Config(JSONWizard, key_case="AUTO"):
    """Tony configuration."""

    log_level: str = "INFO"
