import logging
import wx
import sys
from getopt import getopt
import semver
import requests

from .controller import TonyController
from .constants import APP_NAME, VERSION, PYPI_API_URL, PACKAGE_NAME

help_message = '''
Usage: neuro-api-tony [OPTIONS]

Options:
    -h, --help:
        Show this help message and exit.

    -a, --addr, --address <ADDRESS>:
        The address to start the websocket server on. Default is localhost.

    -l, --log, --log-level <LOG_LEVEL>:
        The log level to use. Default is INFO. Must be one of: DEBUG, INFO,
        WARNING, ERROR, SYSTEM.

    -p, --port <PORT>:
        The port number to start the websocket server on. Default is 8000.

    -v, --version:
        Show the version of the program and exit.
'''

def cli_run() -> None:
    options, _ = getopt(sys.argv[1:], 'ha:l:p:v', ['help', 'addr=', 'address=', 'log=', 'log-level=', 'port=', 'update', 'version'])

    address = 'localhost'
    port = 8000
    log_level = 'INFO'

    for option, value in options:
        match option:
            case '-h' | '--help':
                print(help_message)
                sys.exit(0)

            case '-a' | '--addr' | '--address':
                address = value

            case '-l' | '--log' | '--log-level':
                if value.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'SYSTEM']:
                    print('Invalid log level. Must be one of: DEBUG, INFO, WARNING, ERROR, SYSTEM.')
                    sys.exit(1)
                log_level = value.upper()

            case '-p' | '--port':
                port = int(value)

            case '--update':
                print('This option is deprecated. Please update the program using git or pip.')

                sys.exit(1)

            case '-v' | '--version':
                print(f'{APP_NAME} v{VERSION}')
                sys.exit(0)

    # Check if there are updates available
    try:
        remote_version = requests.get(PYPI_API_URL).json()['info']['version']

        if semver.compare(remote_version, VERSION) > 0:
            print(f'An update is available. ({VERSION} -> {remote_version})\n'
                  f'Depending on your installation method, pull the latest changes from GitHub or\n'
                  f'run "pip install --upgrade {PACKAGE_NAME}" to update.')

    except ConnectionError as exc:
        print('Failed to check for updates. Please check your internet connection.')

    except Exception as exc:
        print('An unknown error occurred while checking for updates.')

    # Start the program
    app = wx.App()
    controller = TonyController(app, log_level)
    controller.run(address, port)

if __name__ == '__main__':
    cli_run()
