"""Controller - Application controller module."""

from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING, Any

import wx
from jsf import JSF

from neuro_api_tony.api import (
    ActionResultCommand,
    ActionsForceCommand,
    ActionsRegisterCommand,
    ActionsUnregisterCommand,
    ContextCommand,
    NeuroAPI,
    ShutdownReadyCommand,
    StartupCommand,
)
from neuro_api_tony.config import (
    ActionScope,
    ConflictPolicy,
    WarningID,
    config,
    get_config_file_path,
    load_config_from_file,
)
from neuro_api_tony.constants import VERSION
from neuro_api_tony.model import NeuroAction, TonyModel
from neuro_api_tony.view import TonyView

if TYPE_CHECKING:
    from collections.abc import Generator


def action_id_generator() -> Generator[str, None, None]:
    """Generate a unique ID for an action."""
    i = 0
    while True:
        yield f"action_{i}"
        i += 1


class TonyController:
    """TonyController class."""

    def __init__(self, app: wx.App, log_level: str) -> None:
        """Initialize Tony Controller."""
        self.app = app
        self.model = TonyModel()
        self.api = NeuroAPI(wx.CallAfter)
        self.view = TonyView(app, self.model, log_level, self.api.on_close)

        self.active_actions_force: ActionsForceCommand | None = None

        self.id_generator = action_id_generator()

        self.inject()

    def run(self, address: str, port: int, init_message: str) -> None:
        """Start websocket server on given address and run GUI main event loop."""
        # Schedule the API start to run after the main loop starts
        wx.CallAfter(self.api.start, address, port)
        wx.CallAfter(self.view.log_info, f"Running version {VERSION}")
        config_file = get_config_file_path()
        if config_file:
            wx.CallAfter(self.view.log_info, f"Loaded configuration from {config_file}")
        if init_message:
            wx.CallAfter(self.view.log_info, init_message)

        self.view.show()
        self.app.MainLoop()

    def inject(self) -> None:
        """Inject methods into the view and API."""
        # fmt: off
        self.api.on_startup = self.on_startup
        self.api.on_context = self.on_context
        self.api.on_actions_register = self.on_actions_register
        self.api.on_actions_unregister = self.on_actions_unregister
        self.api.on_actions_force = self.on_actions_force
        self.api.on_action_result = self.on_action_result
        self.api.on_shutdown_ready = self.on_shutdown_ready
        self.api.on_unknown_command = self.on_unknown_command
        self.api.log_command = self.view.log_command
        self.api.log_debug = self.view.log_debug
        self.api.log_info = self.view.log_info
        self.api.log_warning = self.view.log_warning
        self.api.log_error = self.view.log_error
        self.api.log_critical = self.view.log_critical
        self.api.log_raw = self.view.log_raw
        self.api.get_delay = lambda: float(self.view.controls.latency / 1000)
        self.api.on_client_connect = self.on_client_connect
        self.api.on_client_disconnect = self.on_client_disconnect

        self.view.on_execute = self.on_view_execute
        self.view.on_delete_action = self.on_view_delete_action
        self.view.on_delete_all_actions = self.on_view_delete_all_actions
        self.view.on_unlock = self.on_view_unlock
        self.view.on_clear_logs = self.on_view_clear_logs
        self.view.on_load_config = self.on_view_load_config
        self.view.on_send_actions_reregister_all = self.on_view_send_actions_reregister_all
        self.view.on_send_shutdown_graceful = self.on_view_send_shutdown_graceful
        self.view.on_send_shutdown_graceful_cancel = self.on_view_send_shutdown_graceful_cancel
        self.view.on_send_shutdown_immediate = self.on_view_send_shutdown_immediate

        self.view.get_clients = self.api.get_clients
        # fmt: on

    def on_any_command(self, client_id: int, cmd: Any) -> None:
        """Handle any command received from the API."""

    def on_client_connect(self, client_id: int) -> None:
        """Handle a client connect."""
        self.view.log_info(f"Client {client_id} connected.")

    def on_client_disconnect(self, client_id: int, game: str | None) -> None:
        """Handle a client disconnect."""
        self.view.log_info(f"Closing websocket connection for client id {client_id} ({game}).")
        if config().delete_actions_on_disconnect:
            self.model.remove_actions(client_id=client_id)
            self.view.remove_actions(client_id=client_id)

    def on_startup(self, client_id: int, cmd: StartupCommand) -> None:
        """Handle the startup command."""
        self.view.log_info(f'Client {client_id} started game "{cmd.game}"')

        # Unregister all actions for this game if set to global
        if config().action_scope == ActionScope.GLOBAL:
            actions_to_remove = [action for action in self.view.get_actions() if action.game == cmd.game]
            if actions_to_remove:
                for action in actions_to_remove:
                    self.model.remove_actions(name=action.name)
                    self.view.remove_actions(name=action.name)
                self.view.log_info(
                    f'Removed {len(actions_to_remove)} action(s) previously registered for "{cmd.game}".',
                )

    def on_context(self, client_id: int, cmd: ContextCommand) -> None:
        """Handle the context command."""
        self.view.log_context(cmd.message, client_id, silent=cmd.silent)

    def on_actions_register(self, client_id: int, cmd: ActionsRegisterCommand) -> None:
        """Handle the actions/register command."""
        # Check for actions with the same name
        for action in cmd.actions:
            # Determine whether to check globally or per-client
            check_id = client_id if config().action_scope == ActionScope.CLIENT else None
            if self.view.has_action(name=action.name, client_id=check_id):
                if config().conflict_policy == ConflictPolicy.IGNORE:
                    self.view.log_warning(
                        WarningID.ACTION_NAME_CONFLICT,
                        f'Action "{action.name}" already exists. Ignoring.',
                    )
                    continue
                if config().conflict_policy == ConflictPolicy.OVERWRITE:
                    self.view.log_warning(
                        WarningID.ACTION_NAME_CONFLICT,
                        f'Action "{action.name}" already exists. Overwriting.',
                    )
                    self.model.remove_actions(name=action.name, client_id=check_id)
                    wx.CallAfter(self.view.remove_actions, name=action.name, client_id=check_id)
                elif config().conflict_policy == ConflictPolicy.ALLOW_DUPLICATES:
                    self.view.log_warning(
                        WarningID.ACTION_NAME_CONFLICT,
                        f'Action "{action.name}" already exists. Allowing duplicate.',
                    )
                else:
                    self.view.log_error(
                        f'Unknown conflict policy: {config().conflict_policy}. Cannot register action "{action.name}".',
                    )
                    continue

            self.model.add_action(action)
            wx.CallAfter(self.view.add_action, action)
            self.view.log_description(f"{action.name}: {action.description}", client_id)
        s = "s" if len(cmd.actions) != 1 else ""
        self.view.log_info(f"Action{s} registered: {', '.join(action.name for action in cmd.actions)}")

    def on_actions_unregister(self, client_id: int, cmd: ActionsUnregisterCommand) -> None:
        """Handle the actions/unregister command."""
        known_actions = [name for name in cmd.action_names if self.model.has_action(name)]
        unknown_actions = [name for name in cmd.action_names if not self.model.has_action(name)]
        check_id = client_id if config().action_scope == ActionScope.CLIENT else None
        for name in known_actions:
            self.model.remove_actions(name=name, client_id=check_id)
            self.view.remove_actions(name=name, client_id=check_id)
        s1 = "s" if len(cmd.action_names) != 1 else ""
        s2 = "s" if len(unknown_actions) != 1 else ""
        if known_actions:
            self.view.log_info(f"Action{s1} unregistered: {', '.join(known_actions)}")
        if unknown_actions:
            self.view.log_info(f"Ignoring unregistration of unknown action{s2}: {', '.join(unknown_actions)}")
        if not known_actions and not unknown_actions:
            self.view.log_warning(WarningID.EMPTY_UNREGISTER, "No actions to unregister specified.")

    def on_actions_force(self, client_id: int, cmd: ActionsForceCommand) -> None:
        """Handle the actions/force command."""
        if cmd.state is not None and cmd.state != "":
            self.view.log_state(cmd.state, client_id, cmd.ephemeral_context)
        else:
            self.view.log_info("actions/force command contains no state.")

        self.view.log_query(cmd.query, client_id, cmd.ephemeral_context)

        if self.view.controls.ignore_actions_force:
            self.view.log_info("Forced action ignored.")  # TODO: Make this configurable as warning?
            self.active_actions_force = None
            return

        # Check if all actions exist
        check_id = client_id if config().action_scope == ActionScope.GLOBAL else None
        if not all(self.model.has_action(name) for name in cmd.action_names):
            self.view.log_warning(
                WarningID.ACTIONS_FORCE_INVALID,
                "actions/force with invalid actions received. Discarding.\nInvalid actions: "
                + ", ".join(
                    name for name in cmd.action_names if not self.view.has_action(name=name, client_id=check_id)
                ),
            )
            self.active_actions_force = None
            return

        self.execute_actions_force(client_id, cmd)

    def on_action_result(self, client_id: int, cmd: ActionResultCommand) -> None:
        """Handle the action/result command."""
        self.view.log_info("Action result indicates " + ("success" if cmd.success else "failure"))

        self.view.log_debug(f"cmd.success: {cmd.success}, active_actions_force: {self.active_actions_force}")

        if not cmd.success and self.active_actions_force is not None:
            self.retry_actions_force(client_id, self.active_actions_force)
        else:
            self.active_actions_force = None

        if cmd.message is not None:
            self.view.log_action_result(cmd.success, cmd.message, client_id)
        elif cmd.success:
            self.view.log_info("Successful action result contains no message.")
        else:
            self.view.log_warning(WarningID.NO_ERROR_MESSAGE, "Failed action result contains no message.")

        wx.CallAfter(self.view.on_action_result, cmd.success, cmd.message)

    def on_shutdown_ready(self, client_id: int, cmd: ShutdownReadyCommand) -> None:
        """Handle the shutdown/ready command."""
        self.view.log_info("shutdown/ready is not officially supported.")

    def on_unknown_command(self, client_id: int, json_cmd: Any) -> None:
        """Handle an unknown command."""

        # self.view.log_warning(f'Unknown command received: {json_cmd['command']}')

    def send_action(self, client_id: int, id_: str, name: str, data: str | None) -> bool:
        """Send an action command to the API. Returns True if sent successfully."""
        self.view.log_info(f"Sending action: {name}")
        sent = self.api.send_action(id_, name, data, client_id)

        # Disable the actions until the result is received
        if sent:
            self.view.disable_actions()
        return sent

    def send_actions_reregister_all(self, client_id: int | None) -> None:
        """Send an actions/reregister_all command to the API."""
        self.api.send_actions_reregister_all(client_id)

    def on_view_execute(self, action: NeuroAction) -> bool:
        """Handle an action execution request from the view.

        Returns True if an action was sent, False if the action was cancelled.
        """
        if not action.schema:
            # No schema, so send the action immediately
            return self.send_action(
                action.client_id,
                next(self.id_generator),
                action.name,
                None,
            )

        # If there is a schema, open a dialog to get the data
        result = self.view.show_action_dialog(action)
        if result is None:
            return False  # User cancelled the dialog

        self.model.last_action_data[action.name] = result  # Store the last data in the action object
        return self.send_action(action.client_id, next(self.id_generator), action.name, result)

    def on_view_delete_action(self, client_id: int, name: str) -> None:
        """Handle a request to delete an action from the view."""
        self.model.remove_actions(name=name, client_id=client_id)
        self.view.remove_actions(name=name, client_id=client_id)

        self.view.log_info(f"Action deleted: {name}")

    def on_view_delete_all_actions(self, client_id: int | None) -> None:
        """Handle a request to delete all actions from the view."""
        self.model.remove_actions(client_id=client_id)
        self.view.remove_actions(client_id=client_id)
        if client_id is not None:
            game = self.api.get_game_from_client_id(client_id) or f"provisional_name_{client_id}"
            self.view.log_info(f'All actions deleted for "{game}" (ID: {client_id}).')
        else:
            self.view.log_info("All actions deleted.")

    def on_view_unlock(self) -> None:
        """Handle a request to unlock the view."""
        self.view.log_info("Stopped waiting for action result.")  # TODO: Make this configurable as warning?
        self.view.enable_actions()

    def on_view_clear_logs(self) -> None:
        """Handle a request to clear the logs from the view."""
        self.view.clear_logs()
        self.view.log_info("Logs cleared.")

    def on_view_send_actions_reregister_all(self, client_id: int | None) -> None:
        """Handle a request to send an actions/reregister_all command from the view."""
        self.model.remove_actions(client_id=client_id)
        wx.CallAfter(self.view.remove_actions, client_id=client_id)
        self.send_actions_reregister_all(client_id)

    def on_view_send_shutdown_graceful(self, client_id: int | None) -> None:
        """Handle a request to send a shutdown/graceful command with wants_shutdown=true from the view."""
        self.api.send_shutdown_graceful(True, client_id)

    def on_view_send_shutdown_graceful_cancel(self, client_id: int | None) -> None:
        """Handle a request to send a shutdown/graceful with wants_shutdown=false command from the view."""
        self.api.send_shutdown_graceful(False, client_id)

    def on_view_send_shutdown_immediate(self, client_id: int | None) -> None:
        """Handle a request to send a shutdown/immediate command from the view."""
        self.api.send_shutdown_immediate(client_id)

    def on_view_load_config(self, file_path: str | None = None) -> None:
        """Handle a request to load a configuration file from the view.

        If no file_path is provided, reload the current config file.
        """
        if file_path is None:
            current_file_path = get_config_file_path()
            if current_file_path is None:
                self.view.log_info("No configuration to reload.")
            else:
                self.view.log_info(f"Reloading configuration from {current_file_path}.")
        else:
            self.view.log_info(f"Loading configuration from {file_path}.")
        load_config_from_file(file_path)

    def execute_actions_force(
        self,
        client_id: int,
        cmd: ActionsForceCommand,
        retry: bool = False,
    ) -> None:
        """Handle a request from the game to execute a forced action."""
        self.active_actions_force = cmd

        check_id = client_id if config().action_scope == ActionScope.CLIENT else None
        actions: list[NeuroAction] = []
        for name in cmd.action_names:
            actions.extend(self.view.get_actions(name=name, client_id=check_id))

        if self.view.controls.auto_send:
            self.view.log_info("Automatically sending random action.")
            # S311 - Standard pseudo-random generators are not suitable for cryptographic purposes
            # Not using for cryptographic purposes so we should be fine
            action = random.choice(tuple(actions))  # noqa: S311

            if not action.schema:
                self.send_action(client_id, next(self.id_generator), action.name, None)
            else:
                faker = JSF(action.schema)  # pyright: ignore[reportArgumentType]
                sample = faker.generate()
                self.send_action(
                    client_id,
                    next(self.id_generator),
                    action.name,
                    json.dumps(sample),
                )

        else:
            wx.CallAfter(
                self.view.force_actions,
                cmd.state or "",
                cmd.query,
                cmd.ephemeral_context,
                list(actions),
                cmd.priority,
                retry,
            )

    def retry_actions_force(self, client_id: int, cmd: ActionsForceCommand) -> None:
        """Retry the actions/force command."""
        if self.view.controls.ignore_actions_force:
            self.view.log_info("Forced action ignored.")
            self.active_actions_force = None
            return

        # Check if all actions exist
        if not all(self.model.has_action(name) for name in cmd.action_names):
            self.view.log_warning(
                WarningID.ACTIONS_FORCE_INVALID,
                "Actions have been unregistered before retrying the forced action. Retry aborted.\nInvalid actions: "
                + ", ".join(name for name in cmd.action_names if not self.model.has_action(name)),
            )
            self.active_actions_force = None
            return

        self.view.log_info("Retrying forced action.")

        self.execute_actions_force(client_id, cmd, retry=True)
