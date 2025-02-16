"""API Module - Handles sending and receiving data over the Neuro Websocket API.

See https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md
for more information.
"""

from __future__ import annotations

import json
import traceback
from typing import TYPE_CHECKING, Any, Final, NamedTuple

import jsonschema
import jsonschema.exceptions
import trio
import wx
from trio_websocket import (
    ConnectionClosed,
    WebSocketConnection,
    WebSocketRequest,
    serve_websocket,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from outcome import Outcome

from .model import NeuroAction

ACTION_NAME_ALLOWED_CHARS: Final = "abcdefghijklmnopqrstuvwxyz0123456789_-"

# See https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#action
INVALID_SCHEMA_KEYS: Final = frozenset(
    {
        "$anchor",
        "$comment",
        "$defs",
        "$dynamicAnchor",
        "$dynamicRef",
        "$id",
        "$ref",
        "$schema",
        "$vocabulary",
        "additionalProperties",
        "allOf",
        "anyOf",
        "contentEncoding",
        "contentMediaType",
        "contentSchema",
        "dependentRequired",
        "dependentSchemas",
        "deprecated",
        "description",
        "else",
        "if",
        "maxProperties",
        "minProperties",
        "not",
        "oneOf",
        "patternProperties",
        "readOnly",
        "then",
        "title",
        "unevaluatedItems",
        "unevaluatedProperties",
        "writeOnly",
    },
)


class NeuroAPI:
    """NeuroAPI class."""

    def __init__(self) -> None:
        """Initialize NeuroAPI."""
        self.message_send_channel: trio.MemorySendChannel[str] | None = None
        self.current_game = ""
        self.current_action_id: str | None = None
        self.action_forced = False

        # Dependency injection
        # fmt: off
        self.on_startup: Callable[[StartupCommand], None] = lambda cmd: None
        self.on_context: Callable[[ContextCommand], None] = lambda cmd: None
        self.on_actions_register: Callable[[ActionsRegisterCommand], None] = lambda cmd: None
        self.on_actions_unregister: Callable[[ActionsUnregisterCommand], None] = lambda cmd: None
        self.on_actions_force: Callable[[ActionsForceCommand], None] = lambda cmd: None
        self.on_action_result: Callable[[ActionResultCommand], None] = lambda cmd: None
        self.on_shutdown_ready: Callable[[ShutdownReadyCommand], None] = lambda cmd: None
        self.on_unknown_command: Callable[[Any], None] = lambda cmd: None
        self.log_command: Callable[[str, bool], None] = lambda message, incoming: None
        self.log_debug: Callable[[str], None] = lambda message: None
        self.log_info: Callable[[str], None] = lambda message: None
        self.log_warning: Callable[[str], None] = lambda message: None
        self.log_error: Callable[[str], None] = lambda message: None
        self.log_critical: Callable[[str], None] = lambda message: None
        self.log_raw: Callable[[str, bool], None] = lambda message, incoming: None
        self.get_delay: Callable[[], float] = lambda: 0.0
        # fmt: on

        self.async_library_running = False
        self.async_library_root_cancel: trio.CancelScope
        self.received_loop_close_request = False

    def start(self, address: str, port: int) -> None:
        """Start hosting the websocket server with Trio in the background."""
        if self.received_loop_close_request:
            # Attempting to shut down
            self.log_critical("Something attempted to start websocket server during shutdown, ignoring.")
            return

        if self.async_library_running:
            # Already running, skip
            self.log_critical("Something attempted to start websocket server a 2nd time, ignoring.")
            return

        def done_callback(run_outcome: Outcome[None]) -> None:
            """Handle when trio run completes."""
            assert self.async_library_running, "How can stop running if not running?"
            self.async_library_running = False
            # Unwrap to make sure exceptions are printed
            run_outcome.unwrap()

        self.async_library_running = True
        self.async_library_root_cancel = trio.CancelScope()

        async def root_run() -> None:
            """Root async run, wrapped with async_library_root_cancel so it's able to be stopped remotely."""
            with self.async_library_root_cancel:
                await self._run(address, port)

        try:
            # Start the Trio guest run
            trio.lowlevel.start_guest_run(
                root_run,
                done_callback=done_callback,
                run_sync_soon_threadsafe=wx.CallAfter,
                host_uses_signal_set_wakeup_fd=False,
                restrict_keyboard_interrupt_to_checkpoints=True,
                strict_exception_groups=True,
            )
        except Exception:
            # Make sure async_library_running can never be in invalid state
            # even if trio fails to launch for some reason (shouldn't happen but still)
            self.async_library_running = False
            raise

    def stop(self) -> None:
        """Stop hosting background websocket server."""
        if not self.async_library_running:
            return
        self.async_library_root_cancel.cancel()

    def on_close(self, shutdown_function: Callable[[], None]) -> None:
        """Gracefully handle application quit, cancel async run properly then call shutdown_function."""
        if self.received_loop_close_request:
            self.log_critical("Already closing, ignoring 2nd close request.")
            return

        self.received_loop_close_request = True

        # Already shut down, close
        if not self.async_library_running:
            shutdown_function()
            return

        # Tell trio run to cancel
        try:
            self.stop()
        except Exception:
            # If trigger stop somehow fails, close window
            shutdown_function()

        def shutdown_then_call() -> None:
            # If still running, reschedule this function to run again
            if self.async_library_running:
                wx.CallAfter(shutdown_then_call)
            else:
                # Finally shut down, call shutdown function
                shutdown_function()

        # Schedule `shutdown_function` to be called once trio run closes
        wx.CallAfter(shutdown_then_call)

    async def _run(self, address: str, port: int) -> None:
        """Server run root function."""
        self.log_info(f"Starting websocket server on ws://{address}:{port}.")
        try:
            await serve_websocket(
                self._handle_websocket_request,
                address,
                port,
                ssl_context=None,
            )
        except Exception as exc:
            self.log_critical(f"Failed to start websocket server:\n{exc}")
            raise

    @property
    def client_connected(self) -> bool:
        """Is there a client connected."""
        return self.message_send_channel is not None

    async def _handle_websocket_request(
        self,
        request: WebSocketRequest,
    ) -> None:
        """Handle websocket connection request."""
        if self.client_connected:
            # 503 is "service unavailable"
            await request.reject(
                503,
                body=b"Server does not support multiple connections at once currently",
            )
            self.log_error("Another client attempted to connect, rejecting, server does not support multiple connections at once currently")  # fmt: skip
            return

        try:
            # With blocks for send and receive to handle closing when done
            # Using message_send_channel to send websocket messages synchronously
            # Zero here means no buffer, send not allowed to happen if receive channel has
            # not read prior message waiting yet.
            self.message_send_channel, receive_channel = trio.open_memory_channel[str](0)
            with self.message_send_channel, receive_channel:
                # Accept connection
                async with await request.accept() as connection:
                    await self._handle_client_connection(
                        connection,
                        receive_channel,
                    )
        finally:
            self.message_send_channel = None

    async def _handle_client_connection(
        self,
        websocket: WebSocketConnection,
        receive_channel: trio.MemoryReceiveChannel[str],
    ) -> None:
        """Handle websocket connection lifetime."""
        try:
            async with trio.open_nursery() as nursery:
                # Start running connection read and write tasks in the background
                nursery.start_soon(
                    self._handle_consumer,
                    websocket,
                    nursery.cancel_scope,
                )
                nursery.start_soon(
                    self._handle_producer,
                    websocket,
                    receive_channel,
                )
        except trio.Cancelled:
            self.log_info("Closing current websocket connection.")

    async def _handle_consumer(
        self,
        websocket: WebSocketConnection,
        cancel_scope: trio.CancelScope,
    ) -> None:
        """Handle websocket reading head."""
        while True:
            try:
                # Read message from websocket
                message = await websocket.get_message()
            except ConnectionClosed:
                self.log_info("Websocket connection closed by client.")
                break

            try:
                json_cmd = json.loads(message)
                self.log_raw(json.dumps(json_cmd, indent=2), True)

                game = json_cmd.get("game", {})
                data = json_cmd.get("data", {})

                if game == "" or not isinstance(game, str):
                    self.log_warning("Game name is not set.")
                else:
                    # Check game name
                    if json_cmd["command"] == "startup" or json_cmd["command"] == "game/startup":
                        self.current_game = game
                    elif self.current_game != game:
                        self.log_warning("Game name does not match the current game.")
                    elif self.current_game == "":
                        self.log_warning("No startup command received.")

                # Check action result when waiting for it
                if self.current_action_id is not None and json_cmd["command"] == "actions/force":
                    self.log_warning("Received actions/force while waiting for action/result.")

                # Check if an action is already forced
                if self.action_forced and json_cmd["command"] == "actions/force":
                    self.log_warning("Received actions/force while an action is already forced.")

                # Handle the command
                match json_cmd["command"]:
                    case "startup" | "game/startup":
                        self.log_command(f"{json_cmd['command']}: {game}", True)

                        self.current_action_id = None

                        self.on_startup(StartupCommand())

                        if json_cmd["command"] == "game/startup":
                            self.log_warning('"game/startup" command is deprecated. Use "startup" instead.')

                    case "context":
                        self.log_command("context", True)
                        self.on_context(
                            ContextCommand(data["message"], data["silent"]),
                        )

                    case "actions/register":
                        names = [action["name"] for action in data["actions"]]
                        self.log_command(f"actions/register: {', '.join(names)}", True)

                        # Check the actions
                        for action in data["actions"]:
                            # Check the schema
                            if "schema" in action and action["schema"] != {}:
                                try:
                                    jsonschema.Draft7Validator.check_schema(
                                        action["schema"],
                                    )
                                except jsonschema.exceptions.SchemaError as e:
                                    self.log_error(
                                        f'Invalid schema for action "{action["name"]}": {e}',
                                    )
                                    continue

                                invalid_keys = self.check_invalid_keys_recursive(action["schema"])

                                if len(invalid_keys) > 0:
                                    self.log_warning(f"Disallowed keys in schema: {', '.join(invalid_keys)}")

                            # Check the name
                            if not isinstance(action["name"], str):
                                self.log_error(f"Action name is not a string: {action['name']}")
                                continue

                            if not all(c in ACTION_NAME_ALLOWED_CHARS for c in action["name"]):
                                self.log_warning("Action name is not a lowercase string.")

                            if action["name"] == "":
                                self.log_warning("Action name is empty.")

                        self.on_actions_register(ActionsRegisterCommand(data["actions"]))

                    case "actions/unregister":
                        self.log_command(f"actions/unregister: {', '.join(data['action_names'])}", True)
                        self.on_actions_unregister(ActionsUnregisterCommand(data["action_names"]))

                    case "actions/force":
                        self.action_forced = True
                        self.log_command(f"actions/force: {', '.join(data['action_names'])}", True)
                        self.on_actions_force(
                            ActionsForceCommand(
                                data.get("state"),
                                data["query"],
                                data.get("ephemeral_context", False),
                                data["action_names"],
                            ),
                        )

                    case "action/result":
                        self.log_command(f"action/result: {'success' if data['success'] else 'failure'}", True)

                        # Check if an action/result was expected
                        if self.current_action_id is None:
                            self.log_warning("Unexpected action/result.")
                        # Check if the action ID matches
                        elif self.current_action_id != data["id"]:
                            self.log_warning(f'Received action ID "{data["id"]}" does not match the expected action ID "{self.current_action_id}".')  # fmt: skip

                        self.log_debug(f"Action ID: {data['id']}")

                        self.current_action_id = None
                        self.on_action_result(
                            ActionResultCommand(
                                data["success"],
                                data.get("message", None),
                            ),
                        )

                    case "shutdown/ready":
                        self.log_command("shutdown/ready", True)
                        self.log_warning("This command is not officially supported.")
                        self.on_shutdown_ready(ShutdownReadyCommand())

                    case _:
                        self.log_command(f"{json_cmd['command']}: Unknown command", True)
                        self.log_warning(f"Unknown command: {json_cmd['command']}")
                        self.on_unknown_command(json_cmd)

            except Exception as exc:
                self.log_error(f"Error while handling message: {exc}")
                traceback.print_exception(exc)
                break
        # Cancel (stop) writing head
        cancel_scope.cancel()

    async def _handle_producer(
        self,
        websocket: WebSocketConnection,
        receive_channel: trio.MemoryReceiveChannel[str],
    ) -> None:
        """Handle websocket writing head."""
        while True:
            # Wait for messages from sending side of memory channel (queue)
            message = await receive_channel.receive()

            # Artificial latency
            # Make sure never < 0 or raises ValueError
            await trio.sleep(max(0, self.get_delay()))

            # Write message
            # If connection failure happens, will crash the read head
            # because both share a nursery, ensuring connection closes
            await websocket.send_message(message)

            try:
                self.log_raw(json.dumps(json.loads(message), indent=2), False)
            except json.JSONDecodeError:
                self.log_raw(message, False)

    def _submit_message(self, message: str) -> bool:
        """Submit a message to the send queue. Return True if client connected."""
        if not self.client_connected:
            self.log_error("No client connected!")
            return False
        # Otherwise send channel should exist
        # type checkers need help understanding `self.client_connected`
        assert self.message_send_channel is not None
        self.message_send_channel.send_nowait(message)
        return True

    def send_action(self, id_: str, name: str, data: str | None) -> bool:
        """Send an action command. Return True if actually sent."""
        self.action_forced = False

        payload = {
            "id": id_,
            "name": name,
        }
        if data is not None:
            payload["data"] = data
        obj = {
            "command": "action",
            "data": payload,
        }

        message = json.dumps(obj)

        if not self._submit_message(message):
            return False

        self.current_action_id = id_
        self.log_command(f"action: {name}{' {...}' if data else ''}", False)
        self.log_debug(f"Action ID: {id_}")

        return True

    def send_actions_reregister_all(self) -> bool:
        """Send an actions/reregister_all command."""
        message = json.dumps(
            {
                "command": "actions/reregister_all",
            },
        )

        if not self._submit_message(message):
            return False

        self.log_command("actions/reregister_all", False)
        self.log_warning("This command is not officially supported.")

        return True

    def send_shutdown_graceful(self, wants_shutdown: bool) -> bool:
        """Send a shutdown/graceful command."""
        message = json.dumps(
            {
                "command": "shutdown/graceful",
                "data": {
                    "wants_shutdown": wants_shutdown,
                },
            },
        )

        if not self._submit_message(message):
            return False

        self.log_command(f"shutdown/graceful: wants_shutdown={wants_shutdown}", False)
        self.log_warning("This command is not officially supported.")

        return True

    def send_shutdown_immediate(self) -> bool:
        """Send a shutdown/immediate command."""
        message = json.dumps(
            {
                "command": "shutdown/immediate",
            },
        )

        if not self._submit_message(message):
            return False

        self.log_command("shutdown/immediate", False)
        self.log_warning("This command is not officially supported.")

        return True

    def check_invalid_keys_recursive(
        self,
        sub_schema: dict[str, Any],
    ) -> list[str]:
        """Recursively checks for invalid keys in the schema.

        Returns a list of invalid keys that were found.
        """
        invalid_keys = []

        for key, value in sub_schema.items():
            if key in INVALID_SCHEMA_KEYS:
                invalid_keys.append(key)
            elif isinstance(value, str | int | bool):
                pass
            elif isinstance(value, dict):
                invalid_keys.extend(self.check_invalid_keys_recursive(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        invalid_keys.extend(self.check_invalid_keys_recursive(item))
            else:
                self.log_error(f"Unhandled schema value type {type(value)!r} ({value!r})")

        return invalid_keys


class StartupCommand:
    """`startup` command."""

    __slots__ = ()


class ContextCommand(NamedTuple):
    """`context` command."""

    message: str
    silent: bool


class ActionsRegisterCommand:
    """`actions/register` command."""

    __slots__ = ("actions",)

    def __init__(self, actions: list[dict[str, Any]]) -> None:
        """Initialize actions register command."""
        # 'schema' may be omitted, so get() is used
        self.actions = [
            NeuroAction(
                action["name"],
                action["description"],
                action.get("schema"),
            )
            for action in actions
        ]


class ActionsUnregisterCommand(NamedTuple):
    """`actions/unregister` command."""

    action_names: list[str]


class ActionsForceCommand(NamedTuple):
    """`actions/force` command."""

    state: str | None
    query: str
    ephemeral_context: bool
    action_names: list[str]


class ActionResultCommand(NamedTuple):
    """`action/result` command."""

    success: bool
    message: str | None


class ShutdownReadyCommand:
    """`shutdown/ready` command."""

    __slots__ = ()
