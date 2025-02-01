"""CLI - Command Line Interface module."""

from __future__ import annotations

import sys
import traceback
from getopt import getopt
from typing import Final

import requests
import semver
import wx

from .constants import APP_NAME, PACKAGE_NAME, PYPI_API_URL, VERSION
from .controller import TonyController

HELP_MESSAGE: Final = """
Usage: neuro-api-tony [OPTIONS]

Options:
    -h, --help:
        Show this help message and exit.

    -a, --addr, --address <ADDRESS>:
        The address to start the websocket server on. Default is localhost.

    -l, --log, --log-level <LOG_LEVEL>:
        The log level to use. Default is INFO. Must be one of: DEBUG, INFO,
        WARNING, ERROR, CRITICAL.

    -p, --port <PORT>:
        The port number to start the websocket server on. Default is 8000.

    -v, --version:
        Show the version of the program and exit.
"""


def cli_run() -> None:
    """Command line interface entry point."""
    options, _ = getopt(
        sys.argv[1:],
        "ha:l:p:v",
        [
            "help",
            "addr=",
            "address=",
            "log=",
            "log-level=",
            "port=",
            "update",
            "version",
        ],
    )

    address = "localhost"
    port = 8000
    log_level = "INFO"

    for option, value in options:
        match option:
            case "-h" | "--help":
                print(HELP_MESSAGE)
                sys.exit(0)

            case "-a" | "--addr" | "--address":
                address = value

            case "-l" | "--log" | "--log-level":
                if value.upper() not in [
                    "DEBUG",
                    "INFO",
                    "WARNING",
                    "ERROR",
                    "CRITICAL",
                ]:
                    print("Invalid log level. Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL.")
                    sys.exit(1)
                log_level = value.upper()

            case "-p" | "--port":
                port = int(value)

            case "--update":
                print("This option is deprecated. Please update the program using git or pip.")

                sys.exit(1)

            case "-v" | "--version":
                print(f"{APP_NAME} v{VERSION}")
                sys.exit(0)

    # Check if there are updates available
    try:
        response = requests.get(PYPI_API_URL, timeout=10).json()
        remote_version = response["info"]["version"]

        if semver.compare(remote_version, VERSION) > 0:
            print(
                f"An update is available. ({VERSION} -> {remote_version})\n"
                f"Depending on your installation method, pull the latest changes from GitHub or\n"
                f'run "pip install --upgrade {PACKAGE_NAME}" to update.',
            )

    except ConnectionError:
        print("Failed to check for updates. Please check your internet connection.")

    except Exception as exc:
        print("An error occurred while checking for updates:")
        traceback.print_exception(exc)

    # Start the program
    app = wx.App()
    controller = TonyController(app, log_level)
    controller.run(address, port)


if __name__ == "__main__":
    cli_run()
