import jsonschema._utils
import jsonschema.benchmarks
import jsonschema.exceptions
import jsonschema.tests
import wx

from .model import HumanModel, NeuroAction
from .view import HumanView
from .api import *

def action_id_generator():
    '''Generate a unique ID for an action.'''

    i = 0
    while True:
        yield f'action_{i}'
        i += 1

class HumanController:

    def __init__(self, app: wx.App):
        self.app = app
        self.model = HumanModel()
        self.view = HumanView(app, self.model)
        self.api = NeuroAPI()

        self.id_generator = action_id_generator()

        self.inject()

        self.api.start()

    def run(self):
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
        self.api.log = self.view.log

        self.view.on_execute = self.on_view_execute

    def on_startup(self, cmd: StartupCommand):
        '''Handle the startup command.'''

        self.view.log('startup command received.')
    
    def on_context(self, cmd: ContextCommand):
        '''Handle the context command.'''

        if self.view.is_context_dialog_checked():
            self.view.log('context command received: ' + cmd.message)
            self.view.show_context_dialog(cmd.message)
        else:
            self.view.log('context command received: ' + cmd.message)

    def on_actions_register(self, cmd: ActionsRegisterCommand):
        '''Handle the actions/register command.'''

        self.view.log('actions/register command received.')

        for action in cmd.actions:
            self.model.add_action(action)
            wx.CallAfter(self.view.add_action, action)
            self.view.log(f'Action registered: {action.name}')

    def on_actions_unregister(self, cmd: ActionsUnregisterCommand):
        '''Handle the actions/unregister command.'''

        self.view.log('actions/unregister command received.')

        for name in cmd.action_names:
            self.model.remove_action_by_name(name)
            self.view.remove_action_by_name(name)
            self.view.log(f'Action unregistered: {name}')

    def on_actions_force(self, cmd: ActionsForceCommand):
        '''Handle the actions/force command.'''

        if self.view.is_ignore_actions_force_checked():
            self.view.log('actions/force command received, but ignored.')
            return

        self.view.log('actions/force command received.')

        # self.view.force_actions(cmd.state, cmd.query, cmd.ephemeral_context, cmd.action_names)
        wx.CallAfter(self.view.force_actions, cmd.state, cmd.query, cmd.ephemeral_context, cmd.action_names)

    def on_action_result(self, cmd: ActionResultCommand):
        '''Handle the action/result command.'''

        self.view.log('action/result command received.')

        wx.CallAfter(self.view.on_action_result, cmd.success, cmd.message)

    def on_shutdown_ready(self, cmd: ShutdownReadyCommand):
        '''Handle the shutdown/ready command.'''

        self.view.log('shutdown/ready command received.')

    def on_unknown_command(self, json_cmd: Any):
        '''Handle an unknown command.'''

        self.view.log(f'Unknown command received: {json_cmd['command']}')

    def send_action(self, id: str, name: str, data: str | None):
        '''Send an action command to the API.'''

        self.view.log(f'Sending action: {name}')
        self.api.send_action(id, name, data)

        self.view.disable_actions() # Disable the actions until the result is received

    def send_actions_reregister_all(self):
        '''Send an actions/reregister_all command to the API.'''

        self.view.log('Sending actions/reregister_all command.')
        self.api.send_actions_reregister_all()

    def on_view_execute(self, action: NeuroAction):
        '''Handle an action execution request from the view.'''

        if not action.schema:
            self.send_action(next(self.id_generator), action.name, None) # No schema, so send the action immediately
            return
        
        # If there is a schema, open a dialog to get the data
        result = self.view.show_action_dialog(action)
        if result is None:
            return # User cancelled the dialog
        
        self.send_action(next(self.id_generator), action.name, result)