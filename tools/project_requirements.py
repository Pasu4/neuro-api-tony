#!/usr/bin/env python3

"""Project Requirements - Write test-requirements.in based on pyproject.toml."""

# Programmed by CoolCat467

from __future__ import annotations

# Project Requirements - Write test-requirements.in based on pyproject.toml.
# Copyright (C) 2024  CoolCat467
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__title__ = "Project Requirements"
__author__ = "CoolCat467"
__version__ = "0.0.0"
__license__ = "GNU General Public License Version 3"

import sys
from pathlib import Path
from typing import Final

import tomllib

# Key to start replacing inside of contents
KEY: Final = "TOML_DEPENDENCIES"


def run() -> None:
    """Run program."""
    # Find root folder
    this = Path(__file__).absolute()
    tools = this.parent
    root = tools.parent
    # Make sure it's right
    assert (root / "LICENSE").exists(), "Not in correct directory!"

    # Read pyproject.toml
    pyproject = root / "pyproject.toml"
    with pyproject.open("rb") as fp:
        data = tomllib.load(fp)

    # Get dependencies list
    assert isinstance(data, dict)
    project = data["project"]
    assert isinstance(project, dict)
    dependencies = project["dependencies"]
    assert isinstance(dependencies, list)

    # Read requirements file
    requirements_list = root / "test-requirements.in"
    assert requirements_list.exists(), f"{requirements_list} does not exist!"
    requirements_data = requirements_list.read_text("utf-8")

    # Find out what start and end should be based on key.
    key_start = f"<{KEY}>"
    key_end = f"</{KEY}>"

    # Try to find start and end triggers in requirements data
    start_char = requirements_data.find(key_start)
    end_char = requirements_data.find(key_end)
    if -1 in {start_char, end_char}:
        raise ValueError(
            f"{key_start!r} or {key_end!r} not found in {requirements_list}",
        )

    # Create overwrite text
    dependencies_text = "\n".join(sorted(dependencies))
    overwrite_text = "\n".join(
        (
            key_start,
            dependencies_text,
            f"#{key_end}",
        ),
    )
    # Create new file contents
    end = end_char + len(key_end)
    new_text = (
        requirements_data[:start_char]
        + overwrite_text
        + requirements_data[end:]
    )

    # If new text differs, overwrite and alert
    if new_text != requirements_data:
        print("Requirements file is outdated...")
        requirements_list.write_text(new_text, "utf-8")
        print("Requirements file updated successfully.")
        return 1
    print("Requirements file is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
