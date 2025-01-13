import random

import jsonschema._utils
import jsonschema.benchmarks
import jsonschema.exceptions
import jsonschema.tests
import wx
from jsf import JSF

from .api import *
from .model import NeuroAction, TonyModel
from .view import TonyView


def action_id_generator():
    '''Generate a unique ID for an action.'''

    i = 0
    while True:
        yield f'action_{i}'
        i += 1

class TonyController:

    def __init__(self, app: wx.App, log_level: str):
        self.app = app
        self.model = TonyModel()
        self.view = TonyView(app, self.model, log_level)
        self.api = NeuroAPI()

        self.active_actions_force: ActionsForceCommand | None = None

        self.id_generator = action_id_generator()

        self.inject()

    def run(self, address: str, port: int):
        # Schedule the API start to run after the main loop starts
        wx.CallAfter(self.api.start, address, port)

        self.view.show()
        self.app.MainLoop()

    def inject(self):
        '''Inject methods into the view and API.'''

        self.api.on_startup = self.on_startup
        self.api.on_context = self.on_context
        self.api.on_actions_register = self.on_actions_register
        self.api.on_actions_unregister = self.on_actions_unregister
        self.api.on_actions_force = self.on_actions_force
        self.api.on_action_result = self.on_action_result
        self.api.on_shutdown_ready = self.on_shutdown_ready
        self.api.on_unknown_command = self.on_unknown_command
        self.api.log_system = self.view.log_system
        self.api.log_debug = self.view.log_debug
        self.api.log_info = self.view.log_info
        self.api.log_warning = self.view.log_warning
        self.api.log_error = self.view.log_error
        self.api.log_critical = self.view.log_critical
        self.api.log_raw = self.view.log_raw
        self.api.get_delay = lambda: float(self.view.controls.latency / 1000)

        self.view.on_execute = self.on_view_execute
        self.view.on_delete_action = self.on_view_delete_action
        self.view.on_unlock = self.on_view_unlock
        self.view.on_clear_logs = self.on_view_clear_logs
        self.view.on_send_actions_reregister_all = self.on_view_send_actions_reregister_all
        self.view.on_send_shutdown_graceful = self.on_view_send_shutdown_graceful
        self.view.on_send_shutdown_graceful_cancel = self.on_view_send_shutdown_graceful_cancel
        self.view.on_send_shutdown_immediate = self.on_view_send_shutdown_immediate

    def on_any_command(self, cmd: Any):
        '''Callback for any command received from the API.'''

    def on_startup(self, cmd: StartupCommand):
        '''Handle the startup command.'''

        self.model.clear_actions()
        self.view.clear_actions()

    def on_context(self, cmd: ContextCommand):
        '''Handle the context command.'''

        self.view.log_context(cmd.message, silent=cmd.silent)

    def on_actions_register(self, cmd: ActionsRegisterCommand):
        '''Handle the actions/register command.'''

        for action in cmd.actions:

            # Check if an action with the same name already exists
            if self.model.has_action(action.name):
                self.view.log_warning(f'Action "{action.name}" already exists. Ignoring.')
                continue

            self.model.add_action(action)
            wx.CallAfter(self.view.add_action, action)
            self.view.log_system(f'Action registered: {action.name}')
            self.view.log_description(f'{action.name}: {action.description}')

    def on_actions_unregister(self, cmd: ActionsUnregisterCommand):
        '''Handle the actions/unregister command.'''

        for name in cmd.action_names:
            if not self.model.has_action(name):
                self.view.log_info(f'Action "{name}" does not exist.')

            self.model.remove_action_by_name(name)
            self.view.remove_action_by_name(name)
            self.view.log_system(f'Action unregistered: {name}')

    def on_actions_force(self, cmd: ActionsForceCommand):
        '''Handle the actions/force command.'''

        if cmd.state is not None and cmd.state != '':
            self.view.log_state(cmd.state, cmd.ephemeral_context)
        else:
            self.view.log_info('actions/force command contains no state.')

        self.view.log_query(cmd.query, cmd.ephemeral_context)

        if self.view.controls.ignore_actions_force:
            self.view.log_system('Forced action ignored.')
            self.active_actions_force = None
            return

        # Check if all actions exist
        if not all(self.model.has_action(name) for name in cmd.action_names):
            self.view.log_warning('actions/force with invalid actions received. Discarding.\nInvalid actions: ' + ', '.join(name for name in cmd.action_names if not self.model.has_action(name)))
            self.active_actions_force = None
            return

        self.execute_actions_force(cmd)

    def on_action_result(self, cmd: ActionResultCommand):
        '''Handle the action/result command.'''

        self.view.log_system('Action result indicates ' + ('success' if cmd.success else 'failure'))

        self.view.log_debug(f'cmd.success: {cmd.success}, active_actions_force: {self.active_actions_force}')

        if not cmd.success and self.active_actions_force is not None:
            self.retry_actions_force(self.active_actions_force)
        else:
            self.active_actions_force = None

        if cmd.message is not None:
            self.view.log_action_result(cmd.success, cmd.message)
        elif cmd.success:
            self.view.log_info('Successful action result contains no message.')
        else:
            self.view.log_warning('Failed action result contains no message.')

        wx.CallAfter(self.view.on_action_result, cmd.success, cmd.message)

    def on_shutdown_ready(self, cmd: ShutdownReadyCommand):
        '''Handle the shutdown/ready command.'''

        self.view.log_warning('This command is not officially supported.')

    def on_unknown_command(self, json_cmd: Any):
        '''Handle an unknown command.'''

        # self.view.log_warning(f'Unknown command received: {json_cmd['command']}')

    def send_action(self, id: str, name: str, data: str | None):
        '''Send an action command to the API.'''

        self.view.log_system(f'Sending action: {name}')
        self.api.send_action(id, name, data)

        self.view.disable_actions() # Disable the actions until the result is received

    def send_actions_reregister_all(self):
        '''Send an actions/reregister_all command to the API.'''

        self.api.send_actions_reregister_all()

    def on_view_execute(self, action: NeuroAction) -> bool:
        '''
        Handle an action execution request from the view.
        Returns True if an action was sent, False if the action was cancelled.
        '''

        if not action.schema:
            self.send_action(next(self.id_generator), action.name, None) # No schema, so send the action immediately
            return True

        # If there is a schema, open a dialog to get the data
        result = self.view.show_action_dialog(action)
        if result is None:
            return False # User cancelled the dialog

        self.send_action(next(self.id_generator), action.name, result)
        return True

    def on_view_delete_action(self, name: str):
        '''Handle a request to delete an action from the view.'''

        self.model.remove_action_by_name(name)
        self.view.remove_action_by_name(name)

        self.view.log_system(f'Action deleted: {name}')

    def on_view_unlock(self):
        '''Handle a request to unlock the view.'''

        self.view.log_system('Unlocking actions.')
        self.view.enable_actions()

    def on_view_clear_logs(self):
        '''Handle a request to clear the logs from the view.'''

        self.view.clear_logs()
        self.view.log_system('Logs cleared.')

    def on_view_send_actions_reregister_all(self):
        '''Handle a request to send an actions/reregister_all command from the view.'''

        self.model.clear_actions()
        wx.CallAfter(self.view.clear_actions)
        self.send_actions_reregister_all()

    def on_view_send_shutdown_graceful(self):
        '''Handle a request to send a shutdown/graceful command with wants_shutdown=true from the view.'''

        self.api.send_shutdown_graceful(True)

    def on_view_send_shutdown_graceful_cancel(self):
        '''Handle a request to send a shutdown/graceful with wants_shutdown=false command from the view.'''

        self.api.send_shutdown_graceful(False)

    def on_view_send_shutdown_immediate(self):
        '''Handle a request to send a shutdown/immediate command from the view.'''

        self.api.send_shutdown_immediate()

    def execute_actions_force(self, cmd: ActionsForceCommand, retry: bool = False):
        self.active_actions_force = cmd

        if self.view.controls.auto_send:
            self.view.log_system('Automatically sending random action.')
            actions = [action for action in self.model.actions if action.name in cmd.action_names]
            action = random.choice(actions)

            if action.schema is None:
                self.send_action(next(self.id_generator), action.name, None)
            else:
                faker = JSF(action.schema)
                sample = faker.generate()
                self.send_action(next(self.id_generator), action.name, json.dumps(sample))

        else:
            wx.CallAfter(self.view.force_actions, cmd.state, cmd.query, cmd.ephemeral_context, cmd.action_names, retry)

    def retry_actions_force(self, cmd: ActionsForceCommand):
        '''Retry the actions/force command.'''

        if self.view.controls.ignore_actions_force:
            self.view.log_system('Forced action ignored.')
            self.active_actions_force = None
            return

        # Check if all actions exist
        if not all(self.model.has_action(name) for name in cmd.action_names):
            self.view.log_warning('Actions have been unregistered before retrying the forced action. Retry aborted.\nInvalid actions: ' + ', '.join(name for name in cmd.action_names if not self.model.has_action(name)))
            self.active_actions_force = None
            return

        self.view.log_system('Retrying forced action.')

        self.execute_actions_force(cmd, retry=True)
