import json
from typing import Any, Callable, Optional
import jsonschema
import wx
from datetime import datetime as dt
from jsf import JSF

from .constants import VERSION
from .model import TonyModel, NeuroAction

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

EVT_TYPE_EXECUTE = wx.NewEventType()
EVT_EXECUTE = wx.PyEventBinder(EVT_TYPE_EXECUTE, 1)

class ExecuteEvent(wx.PyCommandEvent):
    '''An event for executing an action.'''

    def __init__(self, id, action: NeuroAction):
        super().__init__(EVT_TYPE_EXECUTE, id)
        self.action = action

#endregion

#region Constants

# Colors
LOG_COLOR_DEFAULT                       = wx.Colour(  0,   0,   0)
LOG_COLOR_TIMESTAMP                     = wx.Colour(  0, 128,   0)
LOG_COLOR_DEBUG                         = wx.Colour(128, 128, 128)
LOG_COLOR_INFO                          = wx.Colour(128, 192, 255)
LOG_COLOR_WARNING                       = wx.Colour(255, 192,   0)
LOG_COLOR_ERROR                         = wx.Colour(255,   0,   0)
LOG_COLOR_CRITICAL                      = wx.Colour(192,   0,   0)
LOG_COLOR_CONTEXT                       = LOG_COLOR_DEFAULT
LOG_COLOR_CONTEXT_QUERY                 = wx.Colour(255, 128, 255)
LOG_COLOR_CONTEXT_STATE                 = wx.Colour(128, 255, 128)
LOG_COLOR_CONTEXT_SILENT                = wx.Colour(128, 128, 128)
LOG_COLOR_CONTEXT_EPHEMERAL             = wx.Colour(128, 192, 255)
LOG_COLOR_CONTEXT_ACTION                = LOG_COLOR_DEFAULT
LOG_COLOR_CONTEXT_ACTION_RESULT_SUCCESS = wx.Colour(  0, 128,   0)
LOG_COLOR_CONTEXT_ACTION_RESULT_FAILURE = wx.Colour(255,   0,   0)
LOG_COLOR_RAW_INCOMING              = wx.Colour(  0,   0, 255)
LOG_COLOR_RAW_OUTGOING              = wx.Colour(255, 128, 192)

UI_COLOR_ERROR = wx.Colour(255, 192, 192)

LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50,
    'SYSTEM': 60,
}

#endregion

class TonyView:
    '''The view class for Tony.'''

    def __init__(self, app: wx.App, model: TonyModel, log_level: str):
        self.model = model

        self.controls = Controls()
        self.controls.set_log_level(log_level)

        self.frame = MainFrame(self)
        app.SetTopWindow(self.frame)

        self.action_dialog: Optional[ActionDialog] = None

        # Dependency injection
        self.on_execute: Callable[[NeuroAction], bool] = lambda action: None
        self.on_delete_action: Callable[[str], None] = lambda name: None
        self.on_unlock: Callable[[], None] = lambda: None
        self.on_clear_logs: Callable[[], None] = lambda: None
        self.on_send_actions_reregister_all: Callable[[], None] = lambda: None
        self.on_send_shutdown_graceful: Callable[[], None] = lambda: None
        self.on_send_shutdown_graceful_cancel: Callable[[], None] = lambda: None
        self.on_send_shutdown_immediate: Callable[[], None] = lambda: None

    def show(self):
        '''Show the main frame.'''

        self.frame.Show()

    def log_system(self, message: str):
        '''Log a command.'''

        if self.controls.get_log_level() <= LOG_LEVELS['SYSTEM']:
            self.frame.panel.log_notebook.log_panel.log(message)

    def log_debug(self, message: str):
        '''Log a debug message.'''

        if self.controls.get_log_level() <= LOG_LEVELS['DEBUG']:
            self.frame.panel.log_notebook.log_panel.log(message, 'Debug', LOG_COLOR_DEBUG)

    def log_info(self, message: str):
        '''Log an informational message.'''

        if self.controls.get_log_level() <= LOG_LEVELS['INFO']:
            self.frame.panel.log_notebook.log_panel.log(message, 'Info', LOG_COLOR_INFO)

    def log_warning(self, message: str):
        '''Log a warning message.'''

        if self.controls.get_log_level() <= LOG_LEVELS['WARNING']:
            self.frame.panel.log_notebook.log_panel.log(message, 'Warning', LOG_COLOR_WARNING)

    def log_error(self, message: str):
        '''Log an error message.'''

        if self.controls.get_log_level() <= LOG_LEVELS['ERROR']:
            self.frame.panel.log_notebook.log_panel.log(message, 'Error', LOG_COLOR_ERROR)

    def log_critical(self, message: str):
        '''Log a critical error message.'''

        if self.controls.get_log_level() <= LOG_LEVELS['CRITICAL']:
            self.frame.panel.log_notebook.log_panel.log(message, 'Critical', LOG_COLOR_CRITICAL)

    def log_context(self, message: str, silent: bool = False):
        '''Log a context message.'''

        tags = ['Context']
        colors = [LOG_COLOR_CONTEXT]

        if silent:
            tags.append('silent')
            colors.append(LOG_COLOR_CONTEXT_SILENT)

        self.frame.panel.log_notebook.context_log_panel.log(message, tags, colors)

    def log_description(self, message: str):
        '''Log an action description.'''

        self.frame.panel.log_notebook.context_log_panel.log(message, 'Action', LOG_COLOR_CONTEXT)

    def log_query(self, message: str, ephemeral: bool = False):
        '''Log an actions/force query.'''

        tags = ['Query']
        colors = [LOG_COLOR_CONTEXT_QUERY]

        if ephemeral:
            tags.append('ephemeral')
            colors.append(LOG_COLOR_CONTEXT_EPHEMERAL)

        self.frame.panel.log_notebook.context_log_panel.log(message, tags, colors)

    def log_state(self, message: str, ephemeral: bool = False):
        '''Log an actions/force state.'''

        tags = ['State']
        colors = [LOG_COLOR_CONTEXT_STATE]

        if ephemeral:
            tags.append('Ephemeral')
            colors.append(LOG_COLOR_CONTEXT_EPHEMERAL)

        self.frame.panel.log_notebook.context_log_panel.log(message, tags, colors)

    def log_action_result(self, success: bool, message: str | None):
        '''Log an action result message.'''

        
        self.frame.panel.log_notebook.context_log_panel.log(message, 'Result', LOG_COLOR_CONTEXT_ACTION_RESULT_SUCCESS if success else LOG_COLOR_CONTEXT_ACTION_RESULT_FAILURE)

    def log_raw(self, message: str, incoming: bool):
        '''Log raw data.'''

        tag = 'Game --> Neuro' if incoming else 'Game <-- Neuro'
        color = LOG_COLOR_RAW_INCOMING if incoming else LOG_COLOR_RAW_OUTGOING

        self.frame.panel.log_notebook.raw_log_panel.log(message, tag, color)

    def clear_logs(self):
        '''Clear all logs.'''

        self.frame.panel.log_notebook.log_panel.text.Clear()
        self.frame.panel.log_notebook.context_log_panel.text.Clear()
        self.frame.panel.log_notebook.raw_log_panel.text.Clear()

    def show_action_dialog(self, action: NeuroAction) -> Optional[str]:
        '''Show a dialog for an action. Returns the JSON string the user entered if "Send" was clicked, otherwise None.'''

        self.action_dialog = ActionDialog(self.frame, action, self.controls.validate_schema)
        result = self.action_dialog.ShowModal()
        text = self.action_dialog.text.GetValue()
        self.action_dialog.Destroy()
        self.action_dialog = None

        if result == wx.ID_OK:
            return text
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

        self.frame.panel.action_list.add_action(action)

    def remove_action_by_name(self, name: str):
        '''Remove an action from the list by name.'''

        self.frame.panel.action_list.remove_action_by_name(name)

    def enable_actions(self):
        '''Enable all action buttons.'''
        
        wx.CallAfter(self.frame.panel.action_list.execute_button.Enable)

    def disable_actions(self):
        '''Disable all action buttons.'''
        
        self.frame.panel.action_list.execute_button.Disable()

    def force_actions(self, state: str, query: str, ephemeral_context: bool, action_names: list[str], retry: bool = False):
        '''Show a dialog for forcing actions.'''

        actions = [action for action in self.model.actions if action.name in action_names]
        actions_force_dialog = ActionsForceDialog(self.frame, self, state, query, ephemeral_context, actions, retry)
        result = actions_force_dialog.ShowModal()
        actions_force_dialog.Destroy()

        # Executing the action has already been handled by the dialog
        if result != wx.ID_OK:
            self.log_system('Manually ignored forced action.')

    def clear_actions(self):
        '''Clear the list of actions.'''

        self.frame.panel.action_list.clear()

    def on_action_result(self, success: bool, message: str | None):
        '''
        Handle an action/result message.
        Enables the execute button.
        '''

        self.enable_actions()

class MainFrame(wx.Frame):
    '''The main frame for the Tony.'''

    def __init__(self, view: TonyView):
        super().__init__(None, title='Tony v' + VERSION)

        self.view = view
        self.panel = MainPanel(self)
        
        best_size: wx.Size = self.panel.GetBestSize()
        self.SetSize((850, 600))

class MainPanel(wx.Panel):
    '''The main panel for Tony.'''

    def __init__(self, parent):
        super().__init__(parent)

        self.action_list = ActionList(self, True)
        right_panel = wx.Panel(self)
        self.log_notebook = LogNotebook(right_panel)
        self.control_panel = ControlPanel(right_panel)

        right_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        right_panel_sizer.Add(self.log_notebook, 1, wx.EXPAND | wx.ALL, 5)
        right_panel_sizer.Add(self.control_panel, 0, wx.EXPAND | wx.ALL, 5)
        right_panel.SetSizer(right_panel_sizer)

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.action_list, 1, wx.EXPAND | wx.ALL, 5)
        self.sizer.Add(right_panel, 1, wx.EXPAND)
        self.SetSizer(self.sizer)
            
class ActionList(wx.Panel):
    '''The list of actions.'''
    
    def __init__(self, parent, can_delete: bool):
        super().__init__(parent, style=wx.BORDER_SUNKEN)

        self.actions: list[NeuroAction] = []

        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        button_panel = wx.Panel(self)
        self.execute_button = wx.Button(button_panel, label='Execute')
        self.delete_button = wx.Button(button_panel, label='Delete')
        self.unlock_button = wx.Button(button_panel, label='Unlock')

        button_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_panel_sizer.Add(self.execute_button, 0, wx.EXPAND | wx.ALL, 5)
        button_panel_sizer.Add(self.delete_button, 0, wx.EXPAND | wx.ALL, 5)
        button_panel_sizer.Add(self.unlock_button, 0, wx.EXPAND | wx.ALL, 5)
        button_panel.SetSizer(button_panel_sizer)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 5)
        self.sizer.Add(button_panel, 0, wx.EXPAND)
        self.SetSizer(self.sizer)

        self.Bind(wx.EVT_BUTTON, self.on_execute, self.execute_button)
        self.Bind(wx.EVT_BUTTON, self.on_delete, self.delete_button)
        self.Bind(wx.EVT_BUTTON, self.on_unlock, self.unlock_button)

        self.list.InsertColumn(0, 'Name', width=150)
        self.list.InsertColumn(1, 'Description', width=240)
        self.list.InsertColumn(2, 'Schema', width=60)

        if not can_delete:
            self.delete_button.Disable()

    def add_action(self, action: NeuroAction):
        '''Add an action panel to the list.'''

        self.actions.append(action)

        self.list.Append([action.name, action.description, 'Yes' if action.schema is not None and action.schema != {} else 'No'])

    def remove_action_by_name(self, name: str):
        '''Remove an action panel from the list.'''

        self.actions = [action for action in self.actions if action.name != name]
        
        index = self.list.FindItem(-1, name)
        if(index != -1):
            self.list.DeleteItem(index)
        # else:
        #     self.GetTopLevelParent().view.log_error(f'Action "{name}" not found in list.')
    
    def clear(self):
        '''Clear the list of actions.'''

        self.actions.clear()
        self.list.DeleteAllItems()

    def on_execute(self, event: wx.CommandEvent):
        event.Skip()

        index = self.list.GetFirstSelected()

        if index == -1:
            return
        
        action = self.actions[index]

        top: MainFrame = self.GetTopLevelParent()
        sent = top.view.on_execute(action)
        
        if sent:
            self.GetEventHandler().ProcessEvent(ExecuteEvent(self.GetId(), action))
        top.view.log_debug(f'Sent: {sent}')

    def on_delete(self, event: wx.CommandEvent):
        event.Skip()

        index = self.list.GetFirstSelected()

        if index == -1:
            return
        
        action: NeuroAction = self.actions[index]

        top: MainFrame = self.GetTopLevelParent()
        top.view.on_delete_action(action.name)

    def on_unlock(self, event: wx.CommandEvent):
        event.Skip()

        top: MainFrame = self.GetTopLevelParent()
        top.view.on_unlock()
    
class LogNotebook(wx.Notebook):
    '''The notebook for logging messages.'''

    def __init__(self, parent):
        super().__init__(parent)

        self.log_panel = LogPanel(self)
        self.context_log_panel = LogPanel(self)
        self.raw_log_panel = LogPanel(self, text_ctrl_style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH | wx.HSCROLL)

        self.AddPage(self.log_panel, 'Log')
        self.AddPage(self.context_log_panel, 'Context')
        self.AddPage(self.raw_log_panel, 'Raw')

class LogPanel(wx.Panel):
    '''The panel for logging messages.'''

    def __init__(self, parent, text_ctrl_style = wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH):
        super().__init__(parent, style=wx.BORDER_SUNKEN)

        self.text = wx.TextCtrl(self, style=text_ctrl_style)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.text, 1, wx.EXPAND)
        self.SetSizer(self.sizer)

    def log(self, message: str, tags: str | list[str] | None = [], tag_colors: wx.Colour | list[wx.Colour] | None = []):
        '''Log a message with optional tags and colors.'''

        # Convert single tags and colors to lists
        if isinstance(tags, str):
            tags = [tags]
        if isinstance(tag_colors, wx.Colour):
            tag_colors = [tag_colors]

        # Convert None to empty lists
        tags = tags or []
        tag_colors = tag_colors or []

        # Add default color for tags without color
        tag_colors += [LOG_COLOR_DEFAULT] * (len(tags) - len(tag_colors))

        # Log timestamp
        self.text.SetDefaultStyle(wx.TextAttr(LOG_COLOR_TIMESTAMP))
        self.text.AppendText(f'[{dt.now().strftime("%X")}] ')
        
        # Log tags
        for tag, tag_color in zip(tags, tag_colors):
            self.text.SetDefaultStyle(wx.TextAttr(tag_color))
            self.text.AppendText(f'[{tag}] ')
        
        # Log message
        self.text.SetDefaultStyle(wx.TextAttr(LOG_COLOR_DEFAULT))
        self.text.AppendText(f'{message}\n')

class ControlPanel(wx.Panel):
    '''The panel for controlling the application.'''

    def __init__(self, parent):
        super().__init__(parent, style=wx.BORDER_SUNKEN)

        self.view: TonyView = self.GetTopLevelParent().view

        # Create controls

        self.validate_schema_checkbox = wx.CheckBox(self, label='Validate JSON schema')
        self.ignore_actions_force_checkbox = wx.CheckBox(self, label='Ignore forced actions')
        self.auto_send_checkbox = wx.CheckBox(self, label='Automatically answer forced actions')

        latency_panel = wx.Panel(self)
        latency_text1 = wx.StaticText(latency_panel, label='L*tency:')
        self.latency_input = wx.TextCtrl(latency_panel, value='0', size=(50, -1))
        latency_text2 = wx.StaticText(latency_panel, label='ms')

        log_level_panel = wx.Panel(self)
        log_level_text = wx.StaticText(log_level_panel, label='Log level:')
        self.log_level_choice = wx.Choice(log_level_panel, choices=[s.capitalize() for s in LOG_LEVELS.keys()])

        self.clear_logs_button = wx.Button(self, label='Clear logs')
        self.send_actions_reregister_all_button = wx.Button(self, label='Clear all actions and request reregistration (experimental)')
        self.send_shutdown_graceful_button = wx.Button(self, label='Request graceful shutdown (experimental)')
        self.send_shutdown_graceful_cancel_button = wx.Button(self, label='Cancel graceful shutdown (experimental)')
        self.send_shutdown_immidiate_button = wx.Button(self, label='Request immediate shutdown (experimental)')

        # Create sizers

        latency_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        latency_panel_sizer.Add(latency_text1, 0, wx.ALL | wx.ALIGN_CENTER, 2)
        latency_panel_sizer.Add(self.latency_input, 0, wx.ALL | wx.ALIGN_CENTER, 2)
        latency_panel_sizer.Add(latency_text2, 0, wx.ALL | wx.ALIGN_CENTER, 2)
        latency_panel.SetSizer(latency_panel_sizer)

        log_lever_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        log_lever_panel_sizer.Add(log_level_text, 0, wx.ALL | wx.ALIGN_CENTER, 2)
        log_lever_panel_sizer.Add(self.log_level_choice, 0, wx.ALL | wx.ALIGN_CENTER, 2)
        log_level_panel.SetSizer(log_lever_panel_sizer)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.validate_schema_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.ignore_actions_force_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.auto_send_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(latency_panel, 0, wx.EXPAND, 0)
        self.sizer.Add(log_level_panel, 0, wx.EXPAND, 0)
        self.sizer.Add(self.clear_logs_button, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.send_actions_reregister_all_button, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.send_shutdown_graceful_button, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.send_shutdown_graceful_cancel_button, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.send_shutdown_immidiate_button, 0, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(self.sizer)

        # Bind events

        self.Bind(wx.EVT_CHECKBOX, self.on_validate_schema, self.validate_schema_checkbox)
        self.Bind(wx.EVT_CHECKBOX, self.on_ignore_actions_force, self.ignore_actions_force_checkbox)
        self.Bind(wx.EVT_CHECKBOX, self.on_auto_send, self.auto_send_checkbox)

        self.Bind(wx.EVT_TEXT, self.on_latency, self.latency_input)

        self.Bind(wx.EVT_CHOICE, self.on_log_level, self.log_level_choice)

        self.Bind(wx.EVT_BUTTON, self.on_clear_logs, self.clear_logs_button)
        self.Bind(wx.EVT_BUTTON, self.on_send_actions_reregister_all, self.send_actions_reregister_all_button)
        self.Bind(wx.EVT_BUTTON, self.on_send_shutdown_graceful, self.send_shutdown_graceful_button)
        self.Bind(wx.EVT_BUTTON, self.on_send_shutdown_graceful_cancel, self.send_shutdown_graceful_cancel_button)
        self.Bind(wx.EVT_BUTTON, self.on_send_shutdown_immediate, self.send_shutdown_immidiate_button)

        # Set default values

        self.validate_schema_checkbox.SetValue(True)
        self.ignore_actions_force_checkbox.SetValue(False)
        self.auto_send_checkbox.SetValue(False)
        # self.latency_input.SetValue('0')
        self.log_level_choice.SetStringSelection(self.view.controls.get_log_level_str())

        # Modify

    def on_clear_logs(self, event: wx.CommandEvent):
        event.Skip()

        self.view.on_clear_logs()

    def on_validate_schema(self, event: wx.CommandEvent):
        event.Skip()

        self.view.controls.validate_schema = event.IsChecked()

    def on_ignore_actions_force(self, event: wx.CommandEvent):
        event.Skip()

        self.view.controls.ignore_actions_force = event.IsChecked()

    def on_auto_send(self, event: wx.CommandEvent):
        event.Skip()

        self.view.controls.auto_send = event.IsChecked()

    def on_latency(self, event: wx.CommandEvent):
        event.Skip()

        try:
            latency = int(self.latency_input.GetValue())
            if latency < 0:
                raise ValueError('Latency must be non-negative.')
            elif latency > 10000:
                raise ValueError('Latency must not exceed 10000 ms.')
            self.view.controls.latency = latency
            self.latency_input.UnsetToolTip()
            self.latency_input.SetBackgroundColour(wx.NullColour) # Default color
        except ValueError as e:
            self.latency_input.SetToolTip(str(e))
            self.latency_input.SetBackgroundColour(UI_COLOR_ERROR)
        self.latency_input.Refresh()

    def on_log_level(self, event: wx.CommandEvent):
        event.Skip()

        sel = self.log_level_choice.GetSelection()
        self.view.controls.set_log_level(self.log_level_choice.GetString(sel))

    def on_send_actions_reregister_all(self, event: wx.CommandEvent):
        event.Skip()

        self.view.on_send_actions_reregister_all()

    def on_send_shutdown_graceful(self, event: wx.CommandEvent):
        event.Skip()

        self.view.on_send_shutdown_graceful()

    def on_send_shutdown_graceful_cancel(self, event: wx.CommandEvent):
        event.Skip()

        self.view.on_send_shutdown_graceful_cancel()

    def on_send_shutdown_immediate(self, event: wx.CommandEvent):
        event.Skip()

        self.view.on_send_shutdown_immediate()

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

    def __init__(self, parent, view: TonyView, state: str, query: str, ephemeral_context: bool, actions: list[NeuroAction], retry: bool = False):
        title = 'Forced Action' if not retry else 'Retry Forced Action'
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.view = view
        self.state = state
        self.query = query
        self.ephemeral_context = ephemeral_context
        self.actions = actions

        self.state_label = wx.StaticText(self, label=f'State: {state}')
        self.query_label = wx.StaticText(self, label=f'Query: {query}')
        self.ephemeral_context_label = wx.StaticText(self, label=f'Ephemeral Context: {ephemeral_context}')
        self.action_list = ActionList(self, False)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.state_label, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.query_label, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.ephemeral_context_label, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.action_list, 1, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(self.sizer)

        for action in actions:
            self.action_list.add_action(action)

        self.action_list.list.Select(0)

        self.Bind(EVT_EXECUTE, self.on_execute, self.action_list)

    def on_execute(self, event: ExecuteEvent):
        event.Skip()

        self.EndModal(wx.ID_OK)

class Controls:
    '''The content of the control panel.'''

    def __init__(self):
        self.validate_schema: bool = True
        self.ignore_actions_force: bool = False
        self.auto_send: bool = False
        self.latency: int = 0

        self.__log_level_str: str = 'INFO'
        self.__log_level: int = LOG_LEVELS['INFO']

    def set_log_level(self, log_level: str):
        '''Set the log level.'''

        self.__log_level_str = log_level
        self.__log_level = LOG_LEVELS[log_level]

    def get_log_level(self) -> int:
        '''Get the log level.'''

        return self.__log_level
    
    def get_log_level_str(self) -> str:
        '''Get the log level as a string.'''

        return self.__log_level_str
    