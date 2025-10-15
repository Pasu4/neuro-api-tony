"""Configuration for Tony."""

from dataclasses import dataclass

from dataclass_wizard import JSONWizard


@dataclass
class Config(JSONWizard, key_case="AUTO"):
    """Tony configuration."""

    conflict_policy: str = "ignoreAlways"
    delete_actions_on_disconnect: bool = True
    log_level: str = "INFO"
