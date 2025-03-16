"""View - Main GUI frame logic."""

from __future__ import annotations

import json
from datetime import datetime as dt
from typing import TYPE_CHECKING

import jsonschema
import wx
from jsf import JSF

from .constants import VERSION

if TYPE_CHECKING:
    from collections.abc import Callable

    from .model import NeuroAction, TonyModel


# region Events

EVTTYPE_ADD_ACTION = wx.NewEventType()
EVT_ADD_ACTION = wx.PyEventBinder(EVTTYPE_ADD_ACTION, 1)


class AddActionEvent(wx.PyCommandEvent):  # type: ignore[misc]
    """An event for adding an action to the list."""

    __slots__ = ("action",)

    def __init__(self, id_: int, action: NeuroAction) -> None:
        """Initialize AddActionEvent."""
        super().__init__(EVTTYPE_ADD_ACTION, id_)
        self.action = action


EVTTYPE_ACTION_RESULT = wx.NewEventType()
EVT_ACTION_RESULT = wx.PyEventBinder(EVTTYPE_ACTION_RESULT, 1)


class ActionResultEvent(wx.PyCommandEvent):  # type: ignore[misc]
    """An event for an action result message."""

    __slots__ = ("message", "success")

    def __init__(self, id_: int, success: bool, message: str | None) -> None:
        """Initialize ActionResultEvent."""
        super().__init__(EVTTYPE_ACTION_RESULT, id_)
        self.success = success
        self.message = message


EVT_TYPE_EXECUTE = wx.NewEventType()
EVT_EXECUTE = wx.PyEventBinder(EVT_TYPE_EXECUTE, 1)


class ExecuteEvent(wx.PyCommandEvent):  # type: ignore[misc]
    """An event for executing an action."""

    __slots__ = ("action",)

    def __init__(self, id_: int, action: NeuroAction) -> None:
        """Initialize ExecuteEvent."""
        super().__init__(EVT_TYPE_EXECUTE, id_)
        self.action = action


# endregion

# region Constants

# Colors
# fmt: off
LOG_COLOR_DEFAULT                       = wx.Colour(  0,   0,   0)
LOG_COLOR_TIMESTAMP                     = wx.Colour(  0, 128,   0)
LOG_COLOR_DEBUG                         = wx.Colour(128, 128, 128)
LOG_COLOR_INFO                          = wx.Colour(128, 192, 255)
LOG_COLOR_WARNING                       = wx.Colour(255, 192,   0)
LOG_COLOR_ERROR                         = wx.Colour(255,   0,   0)
LOG_COLOR_CRITICAL                      = wx.Colour(192,   0,   0)
LOG_COLOR_CONTEXT                       = LOG_COLOR_DEFAULT
LOG_COLOR_CONTEXT_QUERY                 = wx.Colour(255,   0, 255)
LOG_COLOR_CONTEXT_STATE                 = wx.Colour(128, 255, 128)
LOG_COLOR_CONTEXT_SILENT                = wx.Colour(128, 128, 128)
LOG_COLOR_CONTEXT_EPHEMERAL             = wx.Colour(128, 192, 255)
LOG_COLOR_CONTEXT_ACTION                = wx.Colour(  0,   0, 255)
LOG_COLOR_CONTEXT_ACTION_RESULT_SUCCESS = wx.Colour(  0, 128,   0)
LOG_COLOR_CONTEXT_ACTION_RESULT_FAILURE = wx.Colour(255,   0,   0)
LOG_COLOR_INCOMING                      = wx.Colour(  0,   0, 255)
LOG_COLOR_OUTGOING                      = wx.Colour(255,   0, 128)
# fmt: on

UI_COLOR_WARNING = wx.Colour(255, 255, 128)
UI_COLOR_ERROR = wx.Colour(255, 192, 192)

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
    "SYSTEM": 60,
}

LATENCY_TOOLTIP = (
    "Latency in milliseconds to add to each outgoing command."
    " Must be non-negative and not exceed 10000 ms."
)  # fmt: skip

# endregion


class TonyView:
    """The view class for Tony."""

    def __init__(
        self,
        app: wx.App,
        model: TonyModel,
        log_level: str,
        api_close: Callable[[Callable[[], None]], None],
    ) -> None:
        """Initialize TonyView."""
        self.model = model

        self.controls = Controls()
        self.controls.set_log_level(log_level)

        self.frame = MainFrame(self)
        app.SetTopWindow(self.frame)

        self.api_close = api_close
        self.frame.Bind(wx.EVT_CLOSE, self.on_close)

        self.action_dialog: ActionDialog | None = None

        # Dependency injection
        # fmt: off
        self.on_execute: Callable[[NeuroAction], bool] = lambda action: False
        self.on_delete_action: Callable[[str], None] = lambda name: None
        self.on_delete_all_actions: Callable[[], None] = lambda: None
        self.on_unlock: Callable[[], None] = lambda: None
        self.on_clear_logs: Callable[[], None] = lambda: None
        self.on_send_actions_reregister_all: Callable[[], None] = lambda: None
        self.on_send_shutdown_graceful: Callable[[], None] = lambda: None
        self.on_send_shutdown_graceful_cancel: Callable[[], None] = lambda: None
        self.on_send_shutdown_immediate: Callable[[], None] = lambda: None
        # fmt: on

    def on_close(self, event: wx.CloseEvent) -> None:
        """Handle application close event."""
        # Do not let application exit
        event.Veto()
        # Tell api to close async run cleanly and then call destroy this frame
        self.api_close(self.frame.Destroy)

    def show(self) -> None:
        """Show the main frame."""
        self.frame.Show()

    def log_command(self, message: str, incoming: bool) -> None:
        """Log a command."""
        tag = "Game --> Tony" if incoming else "Game <-- Tony"
        color = LOG_COLOR_INCOMING if incoming else LOG_COLOR_OUTGOING

        self.add_export_log(message, tag, "Commands")
        self.frame.panel.log_notebook.command_log_panel.log(message, tag, color)

    def log_debug(self, message: str) -> None:
        """Log a debug message."""
        if self.controls.get_log_level() <= LOG_LEVELS["DEBUG"]:
            self.add_export_log(message, "Debug", "System")
            self.frame.panel.log_notebook.system_log_panel.log(
                message,
                "Debug",
                LOG_COLOR_DEBUG,
            )

    def log_info(self, message: str) -> None:
        """Log an informational message."""
        if self.controls.get_log_level() <= LOG_LEVELS["INFO"]:
            self.add_export_log(message, "Info", "System")
            self.frame.panel.log_notebook.system_log_panel.log(
                message,
                "Info",
                LOG_COLOR_INFO,
            )

    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        if self.controls.get_log_level() <= LOG_LEVELS["WARNING"]:
            self.add_export_log(message, "Warning", "System")
            self.frame.panel.log_notebook.system_log_panel.log(
                message,
                "Warning",
                LOG_COLOR_WARNING,
            )
            self.frame.panel.log_notebook.highlight(LOG_LEVELS["WARNING"])

    def log_error(self, message: str) -> None:
        """Log an error message."""
        if self.controls.get_log_level() <= LOG_LEVELS["ERROR"]:
            self.add_export_log(message, "Error", "System")
            self.frame.panel.log_notebook.system_log_panel.log(
                message,
                "Error",
                LOG_COLOR_ERROR,
            )
            self.frame.panel.log_notebook.highlight(LOG_LEVELS["ERROR"])

    def log_critical(self, message: str) -> None:
        """Log a critical error message."""
        if self.controls.get_log_level() <= LOG_LEVELS["CRITICAL"]:
            self.add_export_log(message, "Critical", "System")
            self.frame.panel.log_notebook.system_log_panel.log(
                message,
                "Critical",
                LOG_COLOR_CRITICAL,
            )
            self.frame.panel.log_notebook.highlight(LOG_LEVELS["CRITICAL"])

    def log_context(self, message: str, silent: bool = False) -> None:
        """Log a context message."""
        tags = []
        colors = []

        if silent:
            tags.append("silent")
            colors.append(LOG_COLOR_CONTEXT_SILENT)

        self.add_export_log(message, tags, "Context")
        self.frame.panel.log_notebook.context_log_panel.log(
            message,
            tags,
            colors,
        )

    def log_description(self, message: str) -> None:
        """Log an action description."""
        self.add_export_log(message, "Action", "Context")
        self.frame.panel.log_notebook.context_log_panel.log(
            message,
            "Action",
            LOG_COLOR_CONTEXT_ACTION,
        )

    def log_query(self, message: str, ephemeral: bool = False) -> None:
        """Log an actions/force query."""
        tags = ["Query"]
        colors = [LOG_COLOR_CONTEXT_QUERY]

        if ephemeral:
            tags.append("ephemeral")
            colors.append(LOG_COLOR_CONTEXT_EPHEMERAL)

        self.add_export_log(message, tags, "Context")
        self.frame.panel.log_notebook.context_log_panel.log(
            message,
            tags,
            colors,
        )

    def log_state(self, message: str, ephemeral: bool = False) -> None:
        """Log an actions/force state."""
        tags = ["State"]
        colors = [LOG_COLOR_CONTEXT_STATE]

        if ephemeral:
            tags.append("Ephemeral")
            colors.append(LOG_COLOR_CONTEXT_EPHEMERAL)

        self.add_export_log(message, tags, "Context")
        self.frame.panel.log_notebook.context_log_panel.log(
            message,
            tags,
            colors,
        )

    def log_action_result(self, success: bool, message: str) -> None:
        """Log an action result message."""
        self.add_export_log(message, ["Result", "Success" if success else "Failure"], "Context")
        self.frame.panel.log_notebook.context_log_panel.log(
            message,
            "Result",
            LOG_COLOR_CONTEXT_ACTION_RESULT_SUCCESS if success else LOG_COLOR_CONTEXT_ACTION_RESULT_FAILURE,
        )

    def log_raw(self, message: str, incoming: bool) -> None:
        """Log raw data."""
        tag = "Game --> Tony" if incoming else "Game <-- Tony"
        color = LOG_COLOR_INCOMING if incoming else LOG_COLOR_OUTGOING

        self.add_export_log(message, tag, "Raw")
        self.frame.panel.log_notebook.raw_log_panel.log(message, tag, color)

    def clear_logs(self) -> None:
        """Clear all logs."""
        self.frame.panel.log_notebook.system_log_panel.text.Clear()
        self.frame.panel.log_notebook.command_log_panel.text.Clear()
        self.frame.panel.log_notebook.context_log_panel.text.Clear()
        self.frame.panel.log_notebook.raw_log_panel.text.Clear()
        self.model.clear_logs()

    def add_export_log(self, message: str, tags: str | list[str] | None, export_tag: str) -> None:
        """Add a log message to the export log."""
        if isinstance(tags, str):
            tags = [tags]
        tags = [dt.now().strftime("%X")] + (tags or [])

        self.model.add_log(export_tag, f"{' '.join(f'[{tag}]' for tag in tags)} {message}")

    def show_action_dialog(self, action: NeuroAction) -> str | None:
        """Show a dialog for an action. Returns the JSON string the user entered if "Send" was clicked, otherwise None."""
        self.action_dialog = ActionDialog(
            self.frame,
            self,
            action,
            self.controls.allow_invalid,
        )
        result = self.action_dialog.ShowModal()
        text = self.action_dialog.text.GetValue()
        self.action_dialog.Destroy()
        self.action_dialog = None

        if result == wx.ID_OK:
            assert isinstance(text, str)
            return text
        return None

    def close_action_dialog(self) -> None:
        """Close the currently opened action dialog.

        Does nothing if no dialog is open.
        Handled as if the "Cancel" button was clicked.
        """
        if self.action_dialog is not None:
            self.action_dialog.EndModal(wx.ID_CANCEL)
            self.action_dialog = None

    def add_action(self, action: NeuroAction) -> None:
        """Add an action to the list."""
        self.frame.panel.action_list.add_action(action)

    def remove_action_by_name(self, name: str) -> None:
        """Remove an action from the list by name."""
        self.frame.panel.action_list.remove_action_by_name(name)

    def enable_actions(self) -> None:
        """Enable executing actions."""
        self.frame.panel.action_list.enable_actions(True)

    def disable_actions(self) -> None:
        """Disable executing actions."""
        self.frame.panel.action_list.enable_actions(False)

    def force_actions(
        self,
        state: str,
        query: str,
        ephemeral_context: bool,
        action_names: list[str],
        retry: bool = False,
    ) -> None:
        """Show a dialog for forcing actions."""
        actions = [action for action in self.model.actions if action.name in action_names]
        actions_force_dialog = ActionsForceDialog(
            self.frame,
            self,
            state,
            query,
            ephemeral_context,
            actions,
            retry,
        )
        result = actions_force_dialog.ShowModal()
        actions_force_dialog.Destroy()

        # Executing the action has already been handled by the dialog
        if result != wx.ID_OK:
            self.log_info("Manually ignored forced action.")

    def clear_actions(self) -> None:
        """Clear the list of actions."""
        self.frame.panel.action_list.clear()

    def on_action_result(self, success: bool, message: str | None) -> None:
        """Handle an action/result message.

        Enables the execute button.
        """
        self.enable_actions()


class MainFrame(wx.Frame):  # type: ignore[misc]
    """The main frame for the Tony."""

    def __init__(self, view: TonyView) -> None:
        """Initialize MainFrame."""
        super().__init__(None, title=f"Tony v{VERSION}")

        self.view = view
        self.panel = MainPanel(self)

        self.SetSize((850, 600))


class MainPanel(wx.Panel):  # type: ignore[misc]
    """The main window for Tony."""

    def __init__(self, parent: MainFrame) -> None:
        """Initialize MainPanel."""
        super().__init__(parent)

        self.action_list = ActionList(self, True)
        right_panel = wx.Panel(self)
        self.log_notebook = LogNotebook(right_panel)
        self.control_panel = ControlPanel(right_panel)

        self.right_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.right_panel_sizer.Add(self.log_notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.right_panel_sizer.Add(self.control_panel, 0, wx.EXPAND | wx.ALL, 5)
        right_panel.SetSizer(self.right_panel_sizer)

        right_panel.SetMinClientSize(self.right_panel_sizer.GetMinSize())
        self.right_panel_sizer.Layout()

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.action_list, 1, wx.EXPAND | wx.ALL, 5)
        self.sizer.Add(right_panel, 1, wx.EXPAND)
        self.SetSizer(self.sizer)

        # Splitter settings

    def maximize_log(self) -> None:
        """Handle maximize event."""
        self.log_notebook.restore_button.Show()
        self.log_notebook.maximize_button.Hide()

        self.control_panel.Hide()
        self.right_panel_sizer.Layout()

        self.action_list.Hide()
        self.sizer.Layout()

    def restore_log(self) -> None:
        """Handle restore event."""
        self.log_notebook.restore_button.Hide()
        self.log_notebook.maximize_button.Show()

        self.control_panel.Show()
        self.right_panel_sizer.Layout()

        self.action_list.Show()
        self.sizer.Layout()


class ActionList(wx.Panel):  # type: ignore[misc]
    """The list of actions."""

    def __init__(
        self,
        parent: MainPanel | ActionsForceDialog,
        can_delete: bool,
    ) -> None:
        """Initialize ActionList panel."""
        super().__init__(parent, style=wx.BORDER_SUNKEN)

        self.can_delete = can_delete
        self.actions_enabled = True

        self.actions: list[NeuroAction] = []

        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.description_text = wx.StaticText(self)
        self.description_text.Hide()
        button_panel = wx.Panel(self)
        self.execute_button = wx.Button(button_panel, label="Execute")
        self.delete_button = wx.Button(button_panel, label="Delete")
        self.delete_all_button = wx.Button(button_panel, label="Delete all")
        self.unlock_button = wx.Button(button_panel, label="Stop waiting")

        button_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_panel_sizer.Add(self.execute_button, 0, wx.EXPAND | wx.ALL, 5)
        button_panel_sizer.Add(self.delete_button, 0, wx.EXPAND | wx.ALL, 5)
        button_panel_sizer.Add(self.delete_all_button, 0, wx.EXPAND | wx.ALL, 5)
        button_panel_sizer.Add(self.unlock_button, 0, wx.EXPAND | wx.ALL, 5)
        button_panel.SetSizer(button_panel_sizer)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 5)
        self.sizer.Add(self.description_text, 0, wx.EXPAND | wx.ALL, 5)
        self.sizer.Add(button_panel, 0, wx.EXPAND)
        self.SetSizer(self.sizer)

        self.Bind(wx.EVT_BUTTON, self.on_execute, self.execute_button)
        self.Bind(wx.EVT_BUTTON, self.on_delete, self.delete_button)
        self.Bind(wx.EVT_BUTTON, self.on_delete_all, self.delete_all_button)
        self.Bind(wx.EVT_BUTTON, self.on_unlock, self.unlock_button)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_execute, self.list)  # ListEvent is a subclass of CommandEvent
        self.Bind(wx.EVT_LIST_KEY_DOWN, self.on_key_down, self.list)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_item_selected, self.list)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_item_deselected, self.list)

        self.list.InsertColumn(0, "Name", width=150)
        self.list.InsertColumn(1, "Description", width=200)
        self.list.InsertColumn(2, "Schema", width=60)

        self.execute_button.SetToolTip(
            "Execute the selected action."
            " Opens a dialog to enter JSON data if the action has a schema.",
        )  # fmt: skip
        self.delete_button.SetToolTip(
            "Delete the selected action."
            " Should only be used for testing, this is not something Neuro would normally do.",
        )
        self.delete_all_button.SetToolTip(
            "Delete all actions."
            " Should only be used for testing, this is not something Neuro would normally do.",
        )  # fmt: skip
        self.unlock_button.SetToolTip("Stop waiting for the game to send an action result.")

        # Setup
        self.execute_button.Disable()
        self.delete_button.Disable()
        self.unlock_button.Disable()

        if not self.can_delete:
            self.delete_all_button.Disable()

    def add_action(self, action: NeuroAction) -> None:
        """Add an action panel to the list."""
        self.actions.append(action)

        self.list.Append(
            [
                action.name,
                action.description,
                "Yes" if action.schema is not None and action.schema != {} else "No",
            ],
        )

    def remove_action_by_name(self, name: str) -> None:
        """Remove an action panel from the list."""
        self.actions = [action for action in self.actions if action.name != name]

        index = self.list.FindItem(-1, name)
        if index != -1:
            self.list.DeleteItem(index)
        # else:
        #     self.GetTopLevelParent().view.log_error(f'Action "{name}" not found in list.')

    def clear(self) -> None:
        """Clear the list of actions."""
        self.actions.clear()
        self.list.DeleteAllItems()

    def enable_actions(self, enable: bool) -> None:
        """Enable or disable executing actions."""
        self.actions_enabled = enable
        self.execute_button.Enable(enable and self.list.GetFirstSelected() != -1)
        self.unlock_button.Enable(not enable)

    def on_execute(self, event: wx.CommandEvent) -> None:
        """Handle execute command event."""
        event.Skip()

        index = self.list.GetFirstSelected()

        if index == -1:
            return

        action = self.actions[index]

        top: MainFrame = self.GetTopLevelParent()
        sent = top.view.on_execute(action)

        if sent:
            self.GetEventHandler().ProcessEvent(ExecuteEvent(self.GetId(), action))
        top.view.log_debug(f"Sent: {sent}")

    def on_delete(self, event: wx.CommandEvent) -> None:
        """Handle delete command event."""
        event.Skip()

        index = self.list.GetFirstSelected()

        if index == -1:
            return

        action: NeuroAction = self.actions[index]

        top: MainFrame = self.GetTopLevelParent()
        top.view.on_delete_action(action.name)

    def on_delete_all(self, event: wx.CommandEvent) -> None:
        """Handle delete all command event."""
        event.Skip()

        top: MainFrame = self.GetTopLevelParent()
        top.view.on_delete_all_actions()

    def on_unlock(self, event: wx.CommandEvent) -> None:
        """Handle unlock command event."""
        event.Skip()

        top: MainFrame = self.GetTopLevelParent()
        top.view.on_unlock()

    def on_key_down(self, event: wx.ListEvent) -> None:
        """Handle key down event."""
        event.Skip()

        if event.GetKeyCode() == wx.WXK_DELETE and self.can_delete:
            self.on_delete(event)

    def on_item_selected(self, event: wx.ListEvent) -> None:
        """Handle item selected event."""
        event.Skip()

        self.execute_button.Enable(self.actions_enabled)
        self.delete_button.Enable(self.can_delete)

        self.description_text.Show()
        self.description_text.SetLabel(self.actions[event.GetIndex()].description)
        self.description_text.Wrap(self.GetClientSize().width - 10)
        self.Layout()

    def on_item_deselected(self, event: wx.ListEvent) -> None:
        """Handle item deselected event."""
        event.Skip()

        self.execute_button.Disable()
        self.delete_button.Disable()

        self.description_text.Hide()
        self.Layout()


class LogNotebook(wx.Panel):  # type: ignore[misc]
    """The notebook for logging messages."""

    def __init__(self, parent: MainPanel) -> None:
        """Initialize Log Notebook."""
        super().__init__(parent)

        self.highlight_level = 0

        # Create controls
        self.notebook = wx.Notebook(self)
        self.system_log_panel = LogPanel(self.notebook)
        self.command_log_panel = LogPanel(self.notebook)
        self.context_log_panel = LogPanel(self.notebook)
        self.raw_log_panel = LogPanel(
            self.notebook,
            text_ctrl_style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH | wx.HSCROLL,
        )

        button_panel = wx.Panel(self)
        self.restore_button = wx.Button(button_panel, label="Restore")
        self.maximize_button = wx.Button(button_panel, label="Maximize")
        self.clear_button = wx.Button(button_panel, label="Clear")
        self.export_button = wx.Button(button_panel, label="Export")
        self.restore_button.Hide()

        self.notebook.AddPage(self.system_log_panel, "System")
        self.notebook.AddPage(self.command_log_panel, "Commands")
        self.notebook.AddPage(self.context_log_panel, "Context")
        self.notebook.AddPage(self.raw_log_panel, "Raw")

        button_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_panel_sizer.Add(self.restore_button, 1, wx.EXPAND | wx.ALL, 2)
        button_panel_sizer.Add(self.maximize_button, 1, wx.EXPAND | wx.ALL, 2)
        button_panel_sizer.Add(self.clear_button, 1, wx.EXPAND | wx.ALL, 2)
        button_panel_sizer.Add(self.export_button, 1, wx.EXPAND | wx.ALL, 2)
        button_panel.SetSizer(button_panel_sizer)

        # Create sizer
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.notebook, 1, wx.EXPAND)
        self.sizer.Add(button_panel, 0, wx.EXPAND | wx.ALL, 0)
        self.SetSizer(self.sizer)

        # Tab icons
        image_list = wx.ImageList(16, 16)
        self.img_warning = image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_WARNING, wx.ART_OTHER, (16, 16)))
        self.img_error = image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_ERROR, wx.ART_OTHER, (16, 16)))
        self.notebook.AssignImageList(image_list)

        # Bind events
        self.Bind(wx.EVT_BUTTON, self.on_restore, self.restore_button)
        self.Bind(wx.EVT_BUTTON, self.on_maximize, self.maximize_button)
        self.Bind(wx.EVT_BUTTON, self.on_clear, self.clear_button)
        self.Bind(wx.EVT_BUTTON, self.on_export, self.export_button)

        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_page_changed, self.notebook)

        # Tooltips
        self.restore_button.SetToolTip("Restore the log panel to its original size.")
        self.maximize_button.SetToolTip("Maximize the log panel to fill the entire window.")
        self.clear_button.SetToolTip("Clear all logs. Exported logs will also be cleared.")
        self.export_button.SetToolTip("Export logs to a file.")

    def highlight(self, level: int) -> None:
        """Highlight the log panel with a color."""
        if self.notebook.GetSelection() == 0:
            return  # Don't highlight when already on the system log

        if self.highlight_level > level:
            return  # Don't replace a highlight of higher level

        image = -1

        if LOG_LEVELS["WARNING"] <= level < LOG_LEVELS["ERROR"]:
            image = self.img_warning

        elif level >= LOG_LEVELS["ERROR"]:
            image = self.img_error

        self.highlight_level = level
        self.notebook.SetPageImage(0, image)

    def reset_highlight(self) -> None:
        """Reset the highlight of the log panel."""
        self.highlight_level = 0
        self.notebook.SetPageImage(0, -1)

    def on_page_changed(self, event: wx.BookCtrlEvent) -> None:
        """Handle page changed event."""
        event.Skip()

        index = event.GetSelection()

        if index == 0:
            self.reset_highlight()

    def on_restore(self, event: wx.CommandEvent) -> None:
        """Handle restore button event."""
        event.Skip()

        top: MainFrame = self.GetTopLevelParent()
        top.panel.restore_log()

    def on_clear(self, event: wx.CommandEvent) -> None:
        """Handle clear command event."""
        event.Skip()

        self.reset_highlight()

        top: MainFrame = self.GetTopLevelParent()
        top.view.on_clear_logs()

    def on_export(self, event: wx.CommandEvent) -> None:
        """Handle export command event."""
        event.Skip()

        with wx.FileDialog(
            self,
            "Export logs",
            wildcard="Log files (*.log)|*.log|Text files (*.txt)|*.txt|All files (*.*)|*.*",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as file_dialog:
            assert isinstance(file_dialog, wx.FileDialog)

            file_dialog.SetFilename(f"tony-{dt.now().strftime('%Y-%m-%d-%H%M%S')}.log")

            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return

            top: MainFrame = self.GetTopLevelParent()
            path = file_dialog.GetPath()
            with open(path, "w") as file:
                file.write(top.view.model.get_logs_formatted())

    def on_maximize(self, event: wx.CommandEvent) -> None:
        """Handle maximize command event."""
        event.Skip()

        top: MainFrame = self.GetTopLevelParent()
        top.panel.maximize_log()


class LogPanel(wx.Panel):  # type: ignore[misc]
    """The panel for logging messages."""

    def __init__(
        self,
        parent: LogNotebook,
        text_ctrl_style: int = wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH,
    ) -> None:
        """Initialize Log Panel."""
        super().__init__(parent, style=wx.BORDER_SUNKEN)

        self.text = wx.TextCtrl(self, style=text_ctrl_style)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.text, 1, wx.EXPAND)
        self.SetSizer(self.sizer)

    def log(
        self,
        message: str,
        tags: str | list[str] | None = None,
        tag_colors: wx.Colour | list[wx.Colour] | None = None,
    ) -> None:
        """Log a message with optional tags and colors."""
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
        top: MainFrame = self.GetTopLevelParent()
        fmt = "%H:%M:%S.%f" if top.view.controls.microsecond_precision else "%H:%M:%S"
        self.text.SetDefaultStyle(wx.TextAttr(LOG_COLOR_TIMESTAMP))
        self.text.AppendText(f"[{dt.now().strftime(fmt)}] ")

        # Log tags
        for tag, tag_color in zip(tags, tag_colors, strict=True):
            self.text.SetDefaultStyle(wx.TextAttr(tag_color))
            self.text.AppendText(f"[{tag}] ")

        # Log message
        self.text.SetDefaultStyle(wx.TextAttr(LOG_COLOR_DEFAULT))
        self.text.AppendText(f"{message}\n")


class ControlPanel(wx.Panel):  # type: ignore[misc]
    """The panel for controlling the application."""

    def __init__(self, parent: MainPanel) -> None:
        """Initialize Control Panel."""
        super().__init__(parent, style=wx.BORDER_SUNKEN)

        self.view: TonyView = self.GetTopLevelParent().view

        # Create controls

        self.ignore_actions_force_checkbox = wx.CheckBox(self, label="Ignore forced actions")
        self.auto_send_checkbox = wx.CheckBox(self, label="Auto-answer")
        self.microsecond_precision_checkbox = wx.CheckBox(self, label="Log microseconds")

        latency_panel = wx.Panel(self)
        latency_text1 = wx.StaticText(latency_panel, label="L*tency:")
        self.latency_input = wx.TextCtrl(latency_panel, value="0", size=(50, -1))
        latency_text2 = wx.StaticText(latency_panel, label="ms")

        log_level_panel = wx.Panel(self)
        log_level_text = wx.StaticText(log_level_panel, label="Log level:")
        self.log_level_choice = wx.Choice(log_level_panel, choices=[s.capitalize() for s in LOG_LEVELS])

        button_panel = wx.Panel(self)
        self.send_actions_reregister_all_button = wx.Button(button_panel, label="Clear and reregister")
        self.send_shutdown_graceful_button = wx.Button(button_panel, label="Graceful shutdown")
        self.send_shutdown_graceful_cancel_button = wx.Button(button_panel, label="Cancel shutdown")
        self.send_shutdown_immediate_button = wx.Button(button_panel, label="Immediate shutdown")

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

        button_panel_sizer = wx.WrapSizer(wx.HORIZONTAL, wx.WRAPSIZER_DEFAULT_FLAGS)
        button_panel_sizer.Add(self.send_actions_reregister_all_button, 0, wx.ALL, 2)
        button_panel_sizer.Add(self.send_shutdown_graceful_button, 0, wx.ALL, 2)
        button_panel_sizer.Add(self.send_shutdown_graceful_cancel_button, 0, wx.ALL, 2)
        button_panel_sizer.Add(self.send_shutdown_immediate_button, 0, wx.ALL, 2)
        button_panel.SetSizer(button_panel_sizer)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.ignore_actions_force_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.auto_send_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.microsecond_precision_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(latency_panel, 0, wx.EXPAND, 0)
        self.sizer.Add(log_level_panel, 0, wx.EXPAND, 0)
        self.sizer.Add(button_panel, 0, wx.EXPAND, 0)
        self.SetSizer(self.sizer)

        wx.CallAfter(self.SendSizeEventToParent)  # For some reason the WrapSizer isn't updated unless this is called

        # Bind events

        self.Bind(wx.EVT_CHECKBOX, self.on_ignore_actions_force, self.ignore_actions_force_checkbox)
        self.Bind(wx.EVT_CHECKBOX, self.on_auto_send, self.auto_send_checkbox)
        self.Bind(wx.EVT_CHECKBOX, self.on_microsecond_precision, self.microsecond_precision_checkbox)

        self.Bind(wx.EVT_TEXT, self.on_latency, self.latency_input)

        self.Bind(wx.EVT_CHOICE, self.on_log_level, self.log_level_choice)

        self.Bind(wx.EVT_BUTTON, self.on_send_actions_reregister_all, self.send_actions_reregister_all_button)
        self.Bind(wx.EVT_BUTTON, self.on_send_shutdown_graceful, self.send_shutdown_graceful_button)
        self.Bind(wx.EVT_BUTTON, self.on_send_shutdown_graceful_cancel, self.send_shutdown_graceful_cancel_button)
        self.Bind(wx.EVT_BUTTON, self.on_send_shutdown_immediate, self.send_shutdown_immediate_button)

        # Set default values

        self.ignore_actions_force_checkbox.SetValue(False)
        self.auto_send_checkbox.SetValue(False)
        self.microsecond_precision_checkbox.SetValue(False)
        self.log_level_choice.SetStringSelection(self.view.controls.get_log_level_str())

        # Add tooltips

        self.ignore_actions_force_checkbox.SetToolTip("Ignore forced actions.")
        self.auto_send_checkbox.SetToolTip(
            "Automatically answer forced actions with randomly generated data (like Randy).",
        )
        self.microsecond_precision_checkbox.SetToolTip("Use microsecond precision for timestamps.")
        self.latency_input.SetToolTip(LATENCY_TOOLTIP)
        self.log_level_choice.SetToolTip(
            "Set the log level. Exported logs will still show all messages."
            "\nDebug: Usually not relevant for normal operation."
            "\nInfo: Might be useful to diagnose issues."
            "\nWarning: A command sent or received does not comply with the API specification."
            "\nError: A command sent or received is invalid and cannot be processed."
            "\nCritical: Tony will likely not be able to recover from this error.",
        )
        self.send_actions_reregister_all_button.SetToolTip(
            "Clear all actions and request reregistration from the game."
            " This is not officially part of the API specification and may not be supported by all SDKs.",
        )
        self.send_shutdown_graceful_button.SetToolTip(
            "Request a graceful shutdown from the game."
            " This is not officially part of the API specification and may not be supported by all SDKs.",
        )
        self.send_shutdown_graceful_cancel_button.SetToolTip(
            "Cancel a graceful shutdown request."
            " This is not officially part of the API specification and may not be supported by all SDKs.",
        )
        self.send_shutdown_immediate_button.SetToolTip(
            "Request an immediate shutdown from the game."
            " This is not officially part of the API specification and may not be supported by all SDKs.",
        )

    def on_ignore_actions_force(self, event: wx.CommandEvent) -> None:
        """Handle ignore_actions_force command event."""
        event.Skip()

        self.view.controls.ignore_actions_force = event.IsChecked()

    def on_auto_send(self, event: wx.CommandEvent) -> None:
        """Handle auto_send command event."""
        event.Skip()

        self.view.controls.auto_send = event.IsChecked()

    def on_microsecond_precision(self, event: wx.CommandEvent) -> None:
        """Handle microsecond_precision command event."""
        event.Skip()

        self.view.controls.microsecond_precision = event.IsChecked()

    def on_latency(self, event: wx.CommandEvent) -> None:
        """Handle latency command event."""
        event.Skip()

        try:
            latency = int(self.latency_input.GetValue())
            if latency < 0:
                raise ValueError("Latency must be non-negative.")
            if latency > 10000:
                raise ValueError("Latency must not exceed 10000 ms.")
            self.view.controls.latency = latency
            self.latency_input.SetToolTip(LATENCY_TOOLTIP)
            self.latency_input.SetBackgroundColour(wx.NullColour)  # Default color
        except ValueError as exc:
            self.latency_input.SetToolTip(str(exc))
            self.latency_input.SetBackgroundColour(UI_COLOR_ERROR)
        self.latency_input.Refresh()

    def on_log_level(self, event: wx.CommandEvent) -> None:
        """Handle log_level command event."""
        event.Skip()

        sel = self.log_level_choice.GetSelection()
        log_level: str = self.log_level_choice.GetString(sel)
        self.view.controls.set_log_level(log_level.upper())

    def on_send_actions_reregister_all(self, event: wx.CommandEvent) -> None:
        """Handle send_actions_reregister_all command event."""
        event.Skip()

        self.view.on_send_actions_reregister_all()

    def on_send_shutdown_graceful(self, event: wx.CommandEvent) -> None:
        """Handle send_shutdown_graceful command event."""
        event.Skip()

        self.view.on_send_shutdown_graceful()

    def on_send_shutdown_graceful_cancel(self, event: wx.CommandEvent) -> None:
        """Handle send_shutdown_graceful_cancel command event."""
        event.Skip()

        self.view.on_send_shutdown_graceful_cancel()

    def on_send_shutdown_immediate(self, event: wx.CommandEvent) -> None:
        """Handle send_shutdown_immediate command event."""
        event.Skip()

        self.view.on_send_shutdown_immediate()


class ActionDialog(wx.Dialog):  # type: ignore[misc]
    """Action dialog."""

    def __init__(
        self,
        parent: MainFrame,
        view: TonyView,
        action: NeuroAction,
        allow_invalid: bool,
    ) -> None:
        """Initialize Action Dialog."""
        super().__init__(parent, title=action.name, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.view = view
        self.action = action

        self.target_sash_ratio = 2 / 3
        self.is_error = False

        self.content_splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        self.text = wx.TextCtrl(self.content_splitter, style=wx.TE_MULTILINE | wx.HSCROLL)
        self.info = wx.TextCtrl(self.content_splitter, style=wx.TE_MULTILINE | wx.HSCROLL | wx.TE_READONLY)
        self.allow_invalid_checkbox = wx.CheckBox(self, label="Don't validate")
        button_panel = wx.Panel(self)
        self.send_button = wx.Button(button_panel, label="Send")
        self.show_schema_button = wx.Button(button_panel, label="Show Schema")
        self.regenerate_button = wx.Button(button_panel, label="Regenerate")
        self.cancel_button = wx.Button(button_panel, label="Cancel")

        button_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_panel_sizer.Add(self.send_button, 0, wx.ALL, 2)
        button_panel_sizer.Add(self.show_schema_button, 0, wx.ALL, 2)
        button_panel_sizer.Add(self.regenerate_button, 0, wx.ALL, 2)
        button_panel_sizer.Add(self.cancel_button, 0, wx.ALL, 2)
        button_panel.SetSizer(button_panel_sizer)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.content_splitter, 1, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.allow_invalid_checkbox, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(button_panel, 0, wx.EXPAND)
        self.SetSizer(self.sizer)

        # Bind events
        self.Bind(wx.EVT_TEXT, self.on_value_change, self.text)
        self.Bind(wx.EVT_CHECKBOX, self.on_allow_invalid, self.allow_invalid_checkbox)
        self.Bind(wx.EVT_BUTTON, self.on_send, self.send_button)
        self.Bind(wx.EVT_BUTTON, self.on_show_schema, self.show_schema_button)
        self.Bind(wx.EVT_BUTTON, self.on_regenerate, self.regenerate_button)
        self.Bind(wx.EVT_BUTTON, self.on_cancel, self.cancel_button)
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.on_sash_pos_changed)
        self.Bind(wx.EVT_SIZE, self.on_size)

        # Set tooltips
        self.allow_invalid_checkbox.SetToolTip("Allow sending invalid JSON data.")
        self.send_button.SetToolTip("Send the JSON data to the client.")
        self.show_schema_button.SetToolTip("Show the JSON schema of the action.")
        self.regenerate_button.SetToolTip("Generate a new random sample.")

        # Setup
        self.content_splitter.Initialize(self.text)
        self.info.Show(False)

        self.info.SetValue(json.dumps(self.action.schema, indent=2))
        self.allow_invalid_checkbox.SetValue(self.view.controls.allow_invalid)

        self.faker = JSF(action.schema)
        self.regenerate()

        self.SetSize((600, 400))

    def regenerate(self) -> None:
        """Regenerate the JSON data."""
        sample = self.faker.generate()
        self.text.SetValue(json.dumps(sample, indent=2))

    def on_value_change(self, event: wx.CommandEvent) -> None:
        """Handle text change."""
        event.Skip()

        try:
            json_str = self.text.GetValue()
            json_cmd = json.loads(json_str)
            jsonschema.validate(json_cmd, self.action.schema)

            self.is_error = False
            self.text.SetToolTip("")
            self.text.SetBackgroundColour(wx.NullColour)
            self.Refresh()
        except Exception as exc:
            self.is_error = True
            self.text.SetToolTip(str(exc))
            self.text.SetBackgroundColour(UI_COLOR_ERROR)
            self.Refresh()

        self.send_button.Enable(self.view.controls.allow_invalid or not self.is_error)

    def on_allow_invalid(self, event: wx.CommandEvent) -> None:
        """Handle allow_invalid command event."""
        event.Skip()

        self.view.controls.allow_invalid = event.IsChecked()
        self.send_button.Enable(self.view.controls.allow_invalid or not self.is_error)

    def on_send(self, event: wx.CommandEvent) -> None:
        """Handle send button."""
        event.Skip()

        try:
            json_str = self.text.GetValue()
            json_cmd = json.loads(json_str)
            if self.view.controls.allow_invalid:
                jsonschema.validate(json_cmd, self.action.schema)

            self.EndModal(wx.ID_OK)
            return

        except Exception as exc:
            if isinstance(exc, jsonschema.ValidationError):
                wx.MessageBox(
                    f"JSON schema validation error: {exc}",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                )
            elif isinstance(exc, json.JSONDecodeError):
                wx.MessageBox(
                    f"JSON decode error: {exc}",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                )
            else:
                raise exc

    def on_show_schema(self, event: wx.CommandEvent) -> None:
        """Handle show schema button."""
        event.Skip()

        self.content_splitter.SplitVertically(self.text, self.info, int(self.GetSize()[0] * self.target_sash_ratio))

    def on_cancel(self, event: wx.CommandEvent) -> None:
        """Handle cancel button."""
        event.Skip()

        self.EndModal(wx.ID_CANCEL)

    def on_regenerate(self, event: wx.CommandEvent) -> None:
        """Handle regenerate command event."""
        event.Skip()

        self.regenerate()

    def on_sash_pos_changed(self, event: wx.SplitterEvent) -> None:
        """Handle sash position changed event."""
        event.Skip()

        if self.content_splitter.IsSplit():
            self.target_sash_ratio = self.content_splitter.GetSashPosition() / self.GetSize()[0]

    def on_size(self, event: wx.SizeEvent) -> None:
        """Handle size event."""
        event.Skip()

        self.content_splitter.SetSashPosition(int(self.target_sash_ratio * self.GetSize()[0]))


class ActionsForceDialog(wx.Dialog):  # type: ignore[misc]
    """Forced Action Dialog."""

    def __init__(
        self,
        parent: MainFrame,
        view: TonyView,
        state: str,
        query: str,
        ephemeral_context: bool,
        actions: list[NeuroAction],
        retry: bool = False,
    ) -> None:
        """Initialize Forced Action Dialog."""
        title = "Forced Action" if not retry else "Retry Forced Action"
        super().__init__(
            parent,
            title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.view = view
        self.state = state
        self.query = query
        self.ephemeral_context = ephemeral_context
        self.actions = actions
        self.formatted_state: str
        try:
            self.formatted_state = json.dumps(json.loads(state), indent=2)
        except (json.JSONDecodeError, TypeError):
            self.formatted_state = state

        state_panel = wx.Panel(self)
        self.state_label = wx.StaticText(state_panel, label="State:")
        self.state_text = wx.StaticText(state_panel, label="")
        self.state_textctrl = wx.TextCtrl(state_panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 100))
        self.state_textctrl.Hide()

        query_panel = wx.Panel(self)
        self.query_label = wx.StaticText(query_panel, label="Query:")
        self.query_text = wx.StaticText(query_panel, label="")

        self.ephemeral_label = wx.StaticText(self, label=f"Ephemeral context: {ephemeral_context}")
        self.action_list = ActionList(self, False)

        state_sizer = wx.BoxSizer(wx.HORIZONTAL)
        state_sizer.Add(self.state_label, 0, wx.TOP | wx.ALL, 2)
        state_sizer.Add(self.state_text, 1, wx.EXPAND | wx.ALL, 2)
        state_sizer.Add(self.state_textctrl, 1, wx.EXPAND | wx.ALL, 2)
        state_panel.SetSizer(state_sizer)

        query_sizer = wx.BoxSizer(wx.HORIZONTAL)
        query_sizer.Add(self.query_label, 0, wx.TOP | wx.ALL, 2)
        query_sizer.Add(self.query_text, 1, wx.EXPAND | wx.ALL, 2)
        query_panel.SetSizer(query_sizer)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(state_panel, 0, wx.EXPAND | wx.ALL, 0)
        self.sizer.Add(query_panel, 0, wx.EXPAND | wx.ALL, 0)
        self.sizer.Add(self.ephemeral_label, 0, wx.EXPAND | wx.ALL, 2)
        self.sizer.Add(self.action_list, 1, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(self.sizer)

        self.sizer.Fit(self)

        # Set tooltips
        self.ephemeral_label.SetToolTip(
            "With ephemeral context, Neuro will not remember the state and query after this action.",
        )

        # Bind events
        self.Bind(EVT_EXECUTE, self.on_execute, self.action_list)

        # Setup
        for action in actions:
            self.action_list.add_action(action)

        self.action_list.list.Select(0)

        # self.state_text.SetBackgroundColour(wx.Colour(255, 255, 255))
        # self.query_text.SetBackgroundColour(wx.Colour(255, 255, 255))

        state_width = self.state_text.GetSize()[0]
        query_width = self.query_text.GetSize()[0]
        self.state_text.SetLabel(self.formatted_state or "<None>")
        self.query_text.SetLabel(query or "<None>")
        self.state_text.Wrap(state_width)
        self.query_text.Wrap(query_width)

        # If state is too large, switch to textctrl
        if self.state_text.GetSize()[1] > 100:
            self.state_text.Hide()
            self.state_textctrl.Show()
            self.state_textctrl.SetValue(self.formatted_state)

        self.Layout()
        self.sizer.Fit(self)

    def on_execute(self, event: ExecuteEvent) -> None:
        """Handle execute command event."""
        event.Skip()

        self.EndModal(wx.ID_OK)


class Controls:
    """The content of the control panel."""

    def __init__(self) -> None:
        """Initialize control panel."""
        self.allow_invalid: bool = False
        self.ignore_actions_force: bool = False
        self.auto_send: bool = False
        self.latency: int = 0
        self.microsecond_precision: bool = False

        self.__log_level_str: str = "INFO"
        self.__log_level: int = LOG_LEVELS["INFO"]

    def set_log_level(self, log_level: str) -> None:
        """Set the log level."""
        self.__log_level_str = log_level
        self.__log_level = LOG_LEVELS[log_level]

    def get_log_level(self) -> int:
        """Get the log level."""
        return self.__log_level

    def get_log_level_str(self) -> str:
        """Get the log level as a string."""
        return self.__log_level_str
