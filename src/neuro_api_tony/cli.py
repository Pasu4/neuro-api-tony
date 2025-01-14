import logging
import wx
import sys
from getopt import getopt
from git import CommandError, GitCommandError, Repo
from git.exc import InvalidGitRepositoryError
import subprocess

from .controller import TonyController
from .constants import APP_NAME, VERSION, GIT_REPO_URL

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

    # Check if the program is a repository and if there are updates available
    try:
        repo = Repo('.')
        repo.remote().fetch()

        if repo.head.commit != repo.remote().refs.master.commit: # Check if the local commit is different from the remote commit
            print('An update is available. To update, pull the latest changes using git.')

    except InvalidGitRepositoryError:
        print('Warning: Update checking is not yet implemented for PyPI distributions. Please\n'
              'check for updates manually until this feature is implemented.')

    except GitCommandError:
        print('Cannot check for updates. Please check your internet connection.')

    # Start the program
    app = wx.App()
    controller = TonyController(app, log_level)
    controller.run(address, port)


if __name__ == '__main__':
    cli_run()
