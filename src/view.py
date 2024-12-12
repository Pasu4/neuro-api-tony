import json
from typing import Any, Callable, Optional
import jsonschema
import wx
from datetime import datetime as dt
from jsf import JSF

from .model import HumanModel, NeuroAction

#region Events

EVTTYPE_ADD_ACTION = wx.NewEventType()
EVT_ADD_ACTION = wx.PyEventBinder(EVTTYPE_ADD_ACTION, 1)

class AddActionEvent(wx.PyCommandEvent):
    '''An event for adding an action to the list.'''

    def __init__(self, id, action: NeuroAction):
        super().__init__(EVTTYPE_ADD_ACTION, id)
        self.action = action

EVTTYPE_ACTION_RESULT = wx.NewEventType()
EVT_ACTION_RESULT = wx.PyEventBinder(EVTTYPE_ACTION_RESULT, 1)

class ActionResultEvent(wx.PyCommandEvent):
    '''An event for an action result message.'''

    def __init__(self, id, success: bool, message: str | None):
        super().__init__(EVTTYPE_ACTION_RESULT, id)
        self.success = success
        self.message = message

#endregion

class HumanView:
    '''The view class for the Human Control application.'''

    def __init__(self, app: wx.App, model: HumanModel):
        self.model = model

        self.frame = MainFrame(self)
        app.SetTopWindow(self.frame)

        self.action_dialog: Optional[ActionDialog] = None
        self.actions_force_dialog: Optional[ActionsForceDialog] = None

        self.on_execute: Callable[[NeuroAction], None] = lambda action: None

    def show(self):
        '''Show the main frame.'''

        self.frame.Show()

    def log(self, message: str):
        '''Log a message.'''

        self.frame.panel.log_panel.log(message)

    def is_context_dialog_checked(self) -> bool:
        '''Return whether to show a dialog for context messages.'''

        return self.frame.panel.control_panel.context_dialog_checkbox.GetValue()
    
    def is_validate_schema_checked(self) -> bool:
        '''Return whether to validate JSON schema.'''

        return self.frame.panel.control_panel.validate_schema_checkbox.GetValue()
    
    def is_ignore_actions_force_checked(self) -> bool:
        '''Return whether to ignore forced actions.'''

        return self.frame.panel.control_panel.ignore_actions_force_checkbox.GetValue()
    
    def is_auto_send_checked(self) -> bool:
        '''Return whether to automatically answer forced actions.'''

        return self.frame.panel.control_panel.auto_send_checkbox.GetValue()
    
    def show_context_dialog(self, message: str) -> None:
        '''Show a dialog for a context message.'''

        wx.MessageBox(message, 'Context', wx.OK | wx.ICON_INFORMATION)

    def show_action_dialog(self, action: NeuroAction) -> Optional[str]:
        '''Show a dialog for an action. Returns the JSON string the user entered if "Send" was clicked, otherwise None.'''

        dialog = ActionDialog(self.frame, action, self.is_validate_schema_checked())
        self.action_dialog = dialog

        if dialog.ShowModal() == wx.ID_OK:
            return dialog.text.GetValue()
        else:
            return None

    def close_action_dialog(self):
        '''
        Close the currently opened action dialog.
        Does nothing if no dialog is open.
        Handled as if the "Cancel" button was clicked.
        '''

        if self.action_dialog is not None:
            self.action_dialog.EndModal(wx.ID_CANCEL)
            self.action_dialog = None

    def add_action(self, action: NeuroAction):
        '''Add an action to the list.'''

        action_panel = ActionPanel(self.frame.panel.action_list_panel, action)
        self.frame.panel.action_list_panel.add_action_panel(action_panel)

    def remove_action_by_name(self, name: str):
        '''Remove an action from the list by name.'''

        action_panel = self.frame.panel.action_list_panel.find_action_panel_by_name(name)
        if action_panel is not None:
            self.frame.panel.action_list_panel.remove_action_panel(action_panel)

    def enable_actions(self):
        '''Enable all action buttons.'''

        if self.actions_force_dialog is not None:
            self.actions_force_dialog.enable_actions()
        
        self.frame.panel.action_list_panel.Enable()

    def disable_actions(self):
        '''Disable all action buttons.'''

        if self.actions_force_dialog is not None:
            self.actions_force_dialog.disable_actions()
        
        self.frame.panel.action_list_panel.Disable()

    def force_actions(self, state: str, query: str, ephemeral_context: bool, action_names: list[str]):
        '''Show a dialog for forcing actions.'''

        actions = [action for action in self.model.actions if action.name in action_names]
        self.actions_force_dialog = ActionsForceDialog(self.frame, self, state, query, ephemeral_context, actions)
        self.actions_force_dialog.ShowModal()

    def on_action_result(self, success: bool, message: str | None):
        '''
        Handle an action/result message.
        If the action was successful, the dialog is closed with wx.ID_OK if it is open.
        Enables all action buttons.
        '''

        if self.actions_force_dialog is not None:
            self.actions_force_dialog.show_result(success, message)
            if success: # Must be retried if unsuccessful
                self.actions_force_dialog.EndModal(wx.ID_OK)
                self.actions_force_dialog = None

        self.enable_actions()

class MainFrame(wx.Frame):
    '''The main frame for the Human Control application.'''

    def __init__(self, view: HumanView):
        super().__init__(None, title='Neuro API Human Control')

        self.view = view
        self.panel = MainPanel(self)
        
        self.SetInitialSize((800, 600))

class MainPanel(wx.Panel):
    '''The main panel for the Human Control application.'''

    def __init__(self, parent):
        super().__init__(parent)

        self.action_list_panel = ActionListPanel(self)
        right_panel = wx.Panel(self)
        self.log_panel = LogPanel(right_panel)
        self.control_panel = ControlPanel(right_panel)

        right_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        right_panel_sizer.Add(self.log_panel, 1, wx.EXPAND | wx.ALL, 5)
        right_panel_sizer.Add(self.control_panel, 0, wx.EXPAND | wx.ALL, 5)
        right_panel.SetSizer(right_panel_sizer)

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.action_list_panel, 1, wx.EXPAND | wx.ALL, 5)
        self.sizer.Add(right_panel, 1, wx.EXPAND)
        self.SetSizer(self.sizer)
            
class ActionListPanel(wx.Panel):
    '''The panel for the list of actions.'''
    
    def __init__(self, parent):
        super().__init__(parent, style=wx.BORDER_SUNKEN)

        self.action_panels: list[ActionPanel] = []

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)

    def add_action_panel(self, action_panel: 'ActionPanel'):
        '''Add an action panel to the list.'''

        self.action_panels.append(action_panel)

        self.sizer.Add(action_panel, 0, wx.EXPAND)
        self.sizer.Layout()
        # self.Fit()

    def remove_action_panel(self, action_panel: wx.Panel):
        '''Remove an action panel from the list.'''

        self.action_panels.remove(action_panel)
        self.sizer.Detach(action_panel)
        
        action_panel.Hide() # For some reason, the panel is not hidden when removed
        action_panel.Destroy()
        self.sizer.Layout()

        # self.Fit()

    def find_action_panel_by_name(self, name: str) -> Optional['ActionPanel']:
        '''Find an action panel by name.'''
        
        for ap in self.action_panels:
            if ap.action.name == name:
                return ap
        
        return None
            
class LogPanel(wx.Panel):
    '''The panel for logging messages.'''

    def __init__(self, parent):
        super().__init__(parent, style=wx.BORDER_SUNKEN)

        self.text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.text, 1, wx.EXPAND)
        self.SetSizer(self.sizer)

    def log(self, message: str):
        self.text.AppendText(f'[{dt.now().strftime("%X")}] {message}\n')

class ControlPanel(wx.Panel):
    '''The panel for controlling the application.'''

    def __init__(self, parent):
        super().__init__(parent, style=wx.BORDER_SUNKEN)

        self.context_dialog_checkbox = wx.CheckBox(self, label='Show a dialog for context messages')
        self.validate_schema_checkbox = wx.CheckBox(self, label='Validate JSON schema')
        self.ignore_actions_force_checkbox = wx.CheckBox(self, label='Ignore forced actions')
        self.auto_send_checkbox = wx.CheckBox(self, label='Automatically answer forced actions')

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.context_dialog_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.validate_schema_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.ignore_actions_force_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.auto_send_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(self.sizer)

        self.context_dialog_checkbox.SetValue(True)
        self.validate_schema_checkbox.SetValue(True)
        self.ignore_actions_force_checkbox.SetValue(False)
        self.auto_send_checkbox.SetValue(False)
            
class ActionPanel(wx.Panel):
    '''The panel for an action.'''

    def __init__(self, parent, action: NeuroAction):
        super().__init__(parent, style=wx.BORDER_SIMPLE, name=action.name)

        self.action = action

        self.name_label = wx.StaticText(self, label=action.name)
        self.execute_button = wx.Button(self, label='Execute')

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.name_label, 1, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.execute_button, 0, wx.ALL | wx.ALIGN_CENTER, 2)
        self.SetSizer(self.sizer)

        self.Bind(wx.EVT_BUTTON, self.on_execute, self.execute_button)

    def on_execute(self, event: wx.CommandEvent):
        event.Skip()

        top: MainFrame = self.GetTopLevelParent()
        top.view.on_execute(self.action)

class ActionDialog(wx.Dialog):

    def __init__(self, parent, action: NeuroAction, do_validate: bool):
        super().__init__(parent, title=action.name)

        self.action = action
        self.do_validate = do_validate

        self.text = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        self.error_label = wx.StaticText(self, label='')
        button_panel = wx.Panel(self)
        self.send_button = wx.Button(button_panel, label='Send')
        self.show_schema_button = wx.Button(button_panel, label='Show Schema')
        self.cancel_button = wx.Button(button_panel, label='Cancel')

        button_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_panel_sizer.Add(self.send_button, 0, wx.ALL, 2)
        button_panel_sizer.Add(self.show_schema_button, 0, wx.ALL, 2)
        button_panel_sizer.Add(self.cancel_button, 0, wx.ALL, 2)
        button_panel.SetSizer(button_panel_sizer)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.error_label, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(button_panel, 0, wx.EXPAND)
        self.SetSizer(self.sizer)

        self.Bind(wx.EVT_BUTTON, self.on_send, self.send_button)
        self.Bind(wx.EVT_BUTTON, self.on_show_schema, self.show_schema_button)
        self.Bind(wx.EVT_BUTTON, self.on_cancel, self.cancel_button)

        faker = JSF(action.schema)
        sample = faker.generate()

        self.text.SetValue(json.dumps(sample, indent=2))

    def on_send(self, event: wx.CommandEvent):
        event.Skip()

        try:
            json_str = self.text.GetValue()
            json_cmd = json.loads(json_str)
            if self.do_validate:
                jsonschema.validate(json_cmd, self.action.schema)
            
            self.EndModal(wx.ID_OK)
            return
        
        except Exception as e:
            if isinstance(e, jsonschema.ValidationError):
                wx.MessageBox(f'JSON schema validation error: {e}', 'Error', wx.OK | wx.ICON_ERROR)
            elif isinstance(e, json.JSONDecodeError):
                wx.MessageBox(f'JSON decode error: {e}', 'Error', wx.OK | wx.ICON_ERROR)
            else:
                raise e

    def on_show_schema(self, event: wx.CommandEvent):
        event.Skip()

        wx.MessageBox(json.dumps(self.action.schema, indent=2), 'Schema', wx.OK | wx.ICON_INFORMATION)

    def on_cancel(self, event: wx.CommandEvent):
        event.Skip()

        self.EndModal(wx.ID_CANCEL)

class ActionsForceDialog(wx.Dialog):

    def __init__(self, parent, view: HumanView, state: str, query: str, ephemeral_context: bool, actions: list[NeuroAction]):
        super().__init__(parent, title='Forced Action', style=wx.DEFAULT_DIALOG_STYLE & ~wx.CLOSE_BOX | wx.RESIZE_BORDER)

        self.view = view
        self.state = state
        self.query = query
        self.ephemeral_context = ephemeral_context
        self.actions = actions

        self.state_label = wx.StaticText(self, label=f'State: {state}')
        self.query_label = wx.StaticText(self, label=f'Query: {query}')
        self.ephemeral_context_label = wx.StaticText(self, label=f'Ephemeral Context: {ephemeral_context}')
        self.action_list_panel = ActionListPanel(self)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.state_label, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.query_label, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.ephemeral_context_label, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.action_list_panel, 1, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(self.sizer)

        for action in actions:
            action_panel = ActionPanel(self.action_list_panel, action)
            self.action_list_panel.add_action_panel(action_panel)

    def show_result(self, success: bool, message: str | None):
        '''Show the result of the forced action.'''

        wx.MessageBox(
            message or 'No message provided.',
            'Action success' if success else 'Action failure',
            wx.OK | wx.ICON_INFORMATION if success else wx.ICON_ERROR
        )

    def enable_actions(self):
        '''Enable all action buttons.'''

        self.action_list_panel.Enable()

    def disable_actions(self):
        '''Disable all action buttons.'''

        self.action_list_panel.Disable()
    