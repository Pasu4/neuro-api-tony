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
Usage: python -m src [options]

Options:
    -h, --help:
        Show this help message and exit.

    -a, --addr, --address:
        The address to start the websocket server on. Default is localhost.

    -l, --log, --log-level:
        The log level to use. Default is INFO. Must be one of: DEBUG, INFO,
        WARNING, ERROR, SYSTEM.

    -p, --port:
        The port number to start the websocket server on. Default is 8000.

    --update:
        Update the program to the latest version, if available. Only works if
        the program is in a git repository.
    
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
                try:
                    repo = Repo('.')

                    print('Checking for updates...')

                    repo.remote().fetch()

                    if repo.head.commit == repo.remote().refs.master.commit: # Check if the local commit is the same as the remote commit
                        print('Program is already up to date.')
                        sys.exit(0)

                    print('Pulling changes from remote repository...')

                    # Only allow fast-forward merges so nothing breaks if the program is modified
                    repo.remote().pull(ff_only=True)

                    if repo.head.commit != repo.remote().refs.master.commit: # Check if the local commit is still different from the remote commit
                        print('Failed to update program.')
                        print('Please update manually using git or reinstall the program from ' + GIT_REPO_URL + '.')
                        sys.exit(1)

                    # Install dependencies
                    print('Installing dependencies...')
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

                    print('Program updated successfully.')
                    sys.exit(0)
                
                except InvalidGitRepositoryError:
                    print('Program is not in a git repository.')
                    print('Please install the new version manually from ' + GIT_REPO_URL + '.')

                except CommandError as e:
                    print(e)
                    print()
                    print('Failed to update program.')
                    print('Please update manually using git or reinstall the program from ' + GIT_REPO_URL + '.')

                except subprocess.CalledProcessError as e:
                    print(e)
                    print()
                    print('Failed to install dependencies.')
                    print('Please install the dependencies manually using pip.')

                sys.exit(1)

            case '-v' | '--version':
                print(f'{APP_NAME} v{VERSION}')
                sys.exit(0)

    # Check if the program is up to date
    try:
        repo = Repo('.')
        repo.remote().fetch()

        if repo.head.commit != repo.remote().refs.master.commit: # Check if the local commit is different from the remote commit
            print('An update is available. Run "python -m src --update" to update.')

    except InvalidGitRepositoryError:
        print('Warning: Update checking is not yet implemented for PyPI distributions. Please check for updates manually until this feature is implemented.')

    except GitCommandError:
        print('Cannot check for updates. Please check your internet connection.')

    # Start the program
    app = wx.App()
    controller = TonyController(app, log_level)
    controller.run(address, port)


if __name__ == '__main__':
    cli_run()
