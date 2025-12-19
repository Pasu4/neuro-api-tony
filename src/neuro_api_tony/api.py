"""API Module - Handles sending and receiving data over the Neuro Websocket API.

See https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md
for more information.
"""

from __future__ import annotations

import traceback
import weakref
from functools import partial
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

import jsonschema
import jsonschema.exceptions
import orjson
import trio
from neuro_api.command import ACTION_NAME_ALLOWED_CHARS, Action, ForcePriority, check_invalid_keys_recursive
from neuro_api.server import AbstractNeuroServerClient, AbstractTrioNeuroServer, ActionSchema
from trio_websocket import (
    ConnectionClosed,
    WebSocketConnection,
    WebSocketRequest,
    serve_websocket,
)

from neuro_api_tony.config import SendActionsTo, WarningID, config
from neuro_api_tony.model import NeuroAction

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

    from outcome import Outcome


class LogCommandProtocol(Protocol):
    """Protocol for `log_command`."""

    def __call__(self, client_id: int, command: str, incoming: bool, addition: str | None = None) -> None:
        """Signature for `log_command`.

        Parameters
        ----------
        client_id : int
            Client id that is logging this command.
        command : str
            The command name.
        incoming : bool
            If `True`, the command was received from the client. If `False`, the command was sent to the client.
        addition : str | None
            An optional additional message. This is used to log additional information about the command, such as the
            game name for the `startup` command.

        """


class NeuroAPIClient(AbstractNeuroServerClient):
    """Neuro API client."""

    __slots__ = ("_client_id", "_server", "game_title", "websocket")

    def __init__(
        self,
        websocket: WebSocketConnection,
        server: NeuroAPI,
        client_id: int,
    ) -> None:
        """Initialize Neuro API client."""
        super().__init__()
        self.websocket = websocket
        self._client_id = client_id

        # Use weak reference to make reference loops impossible (allow
        # server to be garbage collected instead of reference loop)
        self._server = weakref.ref(server)

        self.game_title: str | None = None

    @property
    def server(self) -> NeuroAPI:
        """Bound NeuroAPI Server."""
        server_instance = self._server()
        if server_instance is None:
            raise ValueError("Server reference is dead")
        return server_instance

    def get_next_id(self) -> str:  # noqa: D102
        return self.server.get_next_id()

    async def write_to_websocket(self, data: str) -> None:  # noqa: D102
        await self.websocket.send_message(data)

    async def read_from_websocket(  # noqa: D102
        self,
    ) -> bytes | bytearray | memoryview | str:
        response = await self.websocket.get_message()

        try:
            self.server.log_raw(
                orjson.dumps(
                    orjson.loads(response),
                    option=orjson.OPT_INDENT_2,
                ).decode("utf-8"),
                self._client_id,
                True,
            )
        except orjson.JSONDecodeError:
            if isinstance(response, bytes):
                self.server.log_raw(response.decode("utf-8"), self._client_id, True)
            else:
                self.server.log_raw(response, self._client_id, True)  # pyright: ignore[reportArgumentType]

        return response

    def check_game_title(self, game_title: str) -> None:
        """Log if game title is correct."""
        if self.game_title is None:
            self.server.log_warning(
                WarningID.GAME_NAME_NOT_REGISTERED,
                f"Game name for client {self._client_id} not registered.",
            )
            return
        if self.game_title != game_title:
            self.server.log_warning(
                WarningID.GAME_NAME_MISMATCH,
                f"Game name does not match the registered name for client {self._client_id}.",
            )

    async def handle_startup(  # noqa: D102
        self,
        game_title: str,
    ) -> None:
        if self.game_title is not None:
            self.server.log_warning(
                WarningID.MULTIPLE_STARTUPS,
                f"Startup command received multiple times for {self.game_title}, ignoring.",
            )
        if self.server.get_client_id_from_game(game_title) is not None:
            raise ValueError(f"Another client is already registered as {game_title}.")
        self.game_title = game_title
        self.server.log_command(self._client_id, "startup", True, game_title)
        self.server.on_startup(self._client_id, StartupCommand(game_title))

    async def handle_context(  # noqa: D102
        self,
        game_title: str,
        message: str,
        silent: bool,
    ) -> None:
        self.check_game_title(game_title)
        self.server.log_command(self._client_id, "context", True)
        self.server.on_context(self._client_id, ContextCommand(message, silent))

    async def handle_action_result(  # noqa: D102
        self,
        game_title: str,
        id_: str,
        success: bool,
        message: str | None,
    ) -> None:
        self.check_game_title(game_title)
        self.server.log_command(self._client_id, "action/result", True, "success" if success else "failure")
        self.server.on_action_result(self._client_id, ActionResultCommand(success, message))

    async def handle_actions_force(  # noqa: D102
        self,
        game_title: str,
        state: str | None,
        query: str,
        ephemeral_context: bool,
        action_names: list[str],
        priority: ForcePriority,
    ) -> None:
        self.server.log_command(
            self._client_id,
            "actions/force",
            True,
            f"[{priority.capitalize()}] {', '.join(action_names)}",
        )
        self.server.on_actions_force(
            self._client_id,
            ActionsForceCommand(state, query, ephemeral_context, action_names, priority),
        )

    async def handle_actions_register(  # noqa: D102
        self,
        game_title: str,
        actions: list[Action],
    ) -> None:
        self.check_game_title(game_title)
        self.server.log_command(
            self._client_id,
            "actions/register",
            True,
            ", ".join(action.name for action in actions),
        )

        checked_actions: list[ActionSchema] = []

        # Check the actions
        for action in actions:
            # Check the schema
            if action.schema != {} and action.schema is not None:
                # Neuro API does not allow boolean schemas
                if isinstance(action.schema, bool):
                    self.server.log_error(f"Boolean schemas are not allowed: {action.name}")  # type: ignore[unreachable]
                    continue

                # Check if the schema is valid
                try:
                    jsonschema.Draft7Validator.check_schema(
                        action.schema,
                    )
                except jsonschema.exceptions.SchemaError as e:
                    self.server.log_error(
                        f'Invalid schema for action "{action.name}": {e}',
                    )
                    continue

                invalid_keys = set(check_invalid_keys_recursive(action.schema))
                invalid_keys -= set(config().allowed_schema_keys)

                if len(invalid_keys) > 0:
                    self.server.log_warning(
                        WarningID.ACTION_SCHEMA_UNSUPPORTED,
                        f"Found keys in schema that might be unsupported: {', '.join(invalid_keys)}",
                    )

            # # Check for null schema
            # if action.schema is None:
            #     self.server.log_warning(f"Action schema is null: {action.name}")

            # # Check the name
            # if not isinstance(action.name, str):
            #     self.server.log_error(f"Action name is not a string: {action.name}")  # type: ignore[unreachable]
            #     continue

            if not all(c in ACTION_NAME_ALLOWED_CHARS for c in action.name):
                self.server.log_warning(WarningID.ACTION_NAME_INVALID, "Action name is not a lowercase string.")

            if not action.name:
                self.server.log_warning(WarningID.ACTION_NAME_INVALID, "Action name is empty.")

            # Add the action to the list
            checked_actions.append(action._asdict())  # type: ignore[arg-type]

        self.server.on_actions_register(
            self._client_id,
            ActionsRegisterCommand(
                self._client_id,
                self.game_title or f"provisional_name_{self._client_id}",
                checked_actions,
            ),
        )

    async def handle_actions_unregister(  # noqa: D102
        self,
        game_title: str,
        action_names: list[str],
    ) -> None:
        self.check_game_title(game_title)
        self.server.log_command(self._client_id, "actions/unregister", True, ", ".join(action_names))
        self.server.on_actions_unregister(self._client_id, ActionsUnregisterCommand(action_names))

    async def handle_shutdown_ready(  # noqa: D102
        self,
        game_title: str,
    ) -> None:
        self.check_game_title(game_title)
        self.server.log_command(self._client_id, "shutdown/ready", True)
        self.server.log_info("shutdown/ready (automation API) is not supported by Tony.")
        self.server.on_shutdown_ready(self._client_id, ShutdownReadyCommand())

    async def handle_unknown_command(  # noqa: D102
        self,
        command: str,
        data: dict[str, object] | None,
    ) -> None:
        self.server.log_command(self._client_id, command, True, "Unknown command")
        self.server.log_warning(WarningID.UNKNOWN_COMMAND, f"Unknown command: {command}")
        self.server.on_unknown_command(self._client_id, (command, data))

    async def send_command_data(self, data: bytes) -> None:  # noqa: D102
        await super().send_command_data(data)

        try:
            self.server.log_raw(
                orjson.dumps(
                    orjson.loads(data),
                    option=orjson.OPT_INDENT_2,
                ).decode("utf-8"),
                self._client_id,
                False,
            )
        except orjson.JSONDecodeError:
            self.server.log_raw(data.decode("utf-8"), self._client_id, False)

    def deserialize_actions(  # type: ignore[override]  # noqa: D102
        self,
        data: dict[str, list[object]],
    ) -> list[Action]:
        # actions_data = check_typed_dict(data, RegisterActionsData)

        # Manually check the data because check_typed_dict is too strict
        actions: list[Action] = []
        for raw_action in data["actions"]:
            if not isinstance(raw_action, dict):
                self.server.log_error(f"Action is not an object: {raw_action}")
                continue

            if "name" not in raw_action:
                self.server.log_error(f"Action missing name: {raw_action}")
                continue
            if not isinstance(raw_action["name"], str):
                self.server.log_error(f"Action name is not a string: {raw_action}")
                continue

            if "description" not in raw_action:
                self.server.log_error(f"Action missing description: {raw_action['name']}")
                continue
            if not isinstance(raw_action["description"], str):
                self.server.log_error(f"Action description is not a string: {raw_action}")
                continue

            if "schema" in raw_action:
                if raw_action["schema"] is None:
                    self.server.log_warning(
                        WarningID.ACTION_SCHEMA_NULL,
                        f"Action schema is null: {raw_action['name']}",
                    )
                elif isinstance(raw_action["schema"], bool):
                    self.server.log_error(f"Boolean schemas are not allowed: {raw_action['name']}")
                    continue
                elif not isinstance(raw_action["schema"], dict):
                    self.server.log_error(f"Action schema is not an object: {raw_action}")
                    continue

            if raw_action.keys() - {"name", "description", "schema"}:
                self.server.log_warning(
                    WarningID.ACTION_ADDITIONAL_PROPERTIES,
                    f"Action has additional properties: {', '.join(raw_action.keys() - {'name', 'description', 'schema'})}",
                )

            action = Action(
                raw_action["name"],
                raw_action["description"],
                raw_action.get("schema"),
            )
            actions.append(action)
        return actions


class NeuroAPI(AbstractTrioNeuroServer):
    """NeuroAPI class."""

    def __init__(self, run_sync_soon_threadsafe: Callable[[Callable[[], object]], object]) -> None:
        """Initialize NeuroAPI.

        Parameters
        ----------
        run_sync_soon_threadsafe : Callable[[Callable[[], object]], object]
            A function that is passed to [`trio.lowlevel.start_guest_run`](https://trio.readthedocs.io/en/stable/reference-lowlevel.html#trio.lowlevel.start_guest_run) to run a function in the main thread.
            See the Trio documentation for more information.

        """
        # Tests fail if I rename this to `_run_sync_soon_threadsafe`
        self.run_sync_soon_threadsafe = run_sync_soon_threadsafe

        # Dependency injection
        # fmt: off
        self.on_startup: Callable[[int, StartupCommand], None] = lambda client_id, cmd: None
        """Callback that is called when a [startup](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#startup) command is received.

        Parameters
        ----------
        cmd : StartupCommand
            The received command.
        """
        self.on_context: Callable[[int, ContextCommand], None] = lambda client_id, cmd: None
        """Callback that is called when a [context](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#context) command is received.

        Parameters
        ----------
        cmd : ContextCommand
            The received command.
        """
        self.on_actions_register: Callable[[int, ActionsRegisterCommand], None] = lambda client_id, cmd: None
        """Callback that is called when an [actions/register](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#register-actions) command is received.

        Parameters
        ----------
        cmd : ActionsRegisterCommand
            The received command.
        """
        self.on_actions_unregister: Callable[[int, ActionsUnregisterCommand], None] = lambda client_id, cmd: None
        """Callback that is called when an [actions/unregister](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#unregister-actions) command is received.

        Parameters
        ----------
        cmd : ActionsUnregisterCommand
            The received command.
        """
        self.on_actions_force: Callable[[int, ActionsForceCommand], None] = lambda client_id, cmd: None
        """Callback that is called when an [actions/force](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#force-actions) command is received.

        Parameters
        ----------
        cmd : ActionsForceCommand
            The received command.
        """
        self.on_action_result: Callable[[int, ActionResultCommand], None] = lambda client_id, cmd: None
        """Callback that is called when an [action/result](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#action-result) command is received.

        Parameters
        ----------
        cmd : ActionResultCommand
            The received command.
        """
        self.on_shutdown_ready: Callable[[int, ShutdownReadyCommand], None] = lambda client_id, cmd: None
        """Callback that is called when a [shutdown/ready](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md#shutdown-ready) command is received.

        Parameters
        ----------
        cmd : ShutdownReadyCommand
            The received command.
        """
        self.on_unknown_command: Callable[[int, Any], None] = lambda client_id, cmd: None
        """Callback that is called when an unknown command is received.

        Parameters
        ----------
        cmd : Any
            The received command.
        """
        self.log_command: LogCommandProtocol = lambda client_id, command, incoming, addition=None: None
        """
        log_command(command, incoming, addition)

        Logging callback that is called when a command is received.

        Parameters
        ----------
        command : str
            The command name.
        incoming : bool
            If `True`, the command was received from the client. If `False`, the command was sent to the client.
        addition : str, optional
            An optional additional message. This is used to log additional information about the command, such as the
            game name for the `startup` command.
        """
        self.log_debug: Callable[[str], None] = lambda message: None
        """Logging callback that is called when a debug message should be logged.

        Parameters
        ----------
        message : str
            The message to log.

        """
        self.log_info: Callable[[str], None] = lambda message: None  # type: ignore[assignment]
        """Logging callback that is called when an info message should be logged.

        Parameters
        ----------
        message : str
            The message to log.

        """
        self.log_warning: Callable[[WarningID, str], None] = lambda warning_id, message: None  # type: ignore[assignment]
        """Logging callback that is called when a warning message should be logged.

        Parameters
        ----------
        message : str
            The message to log.

        """
        self.log_error: Callable[[str], None] = lambda message: None
        """Logging callback that is called when an error message should be logged.

        Parameters
        ----------
        message : str
            The message to log.

        """
        self.log_critical: Callable[[str], None] = lambda message: None  # type: ignore[assignment]
        """Logging callback that is called when a critical error message should be logged.

        If a critical error occurs, the API instance is in an invalid state and should not be used anymore.

        Parameters
        ----------
        message : str
            The message to log.

        """
        self.log_raw: Callable[[str, int, bool], None] = lambda message, client_id, incoming: None
        """Logging callback that is called when any message is received or sent.

        Parameters
        ----------
        message : str
            The raw JSON data received or sent.
        client_id : int
            The client id that sent or received the message.
        incoming : bool
            If `True`, the message was received from the client. If `False`, the message was sent to the client.

        """
        self.get_delay: Callable[[], float] = lambda: 0.0
        """A function that should return the delay in seconds to wait before sending a message.

        Returns
        -------
        float
            The delay in seconds to wait before sending a message.
        """
        self.on_client_connect: Callable[[int], None] = lambda client_id: None
        """Callback that is called when a client connects."""
        self.on_client_disconnect: Callable[[int, str | None], None] = lambda client_id, game: None
        """Callback that is called when a client disconnects."""
        # fmt: on

        self._async_library_running = False
        self._async_library_root_cancel: trio.CancelScope
        self._received_loop_close_request = False
        self._next_command_id = 0

        self._next_client_id = 0
        self._clients: dict[
            int,
            tuple[NeuroAPIClient, trio.MemorySendChannel[partial[Awaitable[Any]] | partial[Coroutine[Any, Any, Any]]]],
        ] = {}

    def get_next_id(self) -> str:
        """Generate and return the next unique command identifier."""
        value = self._next_command_id
        self._next_command_id += 1
        return f"tony_action_{value}"

    def get_game_from_client_id(self, client_id: int) -> str | None:
        """Get the game title of a client by its id."""
        client = self._clients.get(client_id)
        if client:
            return client[0].game_title
        return None

    def get_client_id_from_game(self, game_title: str) -> int | None:
        """Get the client id of a client by its game title."""
        for client_id, (client, _) in self._clients.items():
            if client.game_title == game_title:
                return client_id
        return None

    def get_clients(self) -> list[tuple[int, str | None]]:
        """Get a list of connected clients as (client_id, game_title) tuples."""
        return [(client_id, client.game_title) for client_id, (client, _) in self._clients.items()]

    async def choose_force_action(  # noqa: D102
        self,
        game_title: str | None,
        state: str | None,
        query: str,
        ephemeral_context: bool,
        actions: tuple[Action, ...],
        priority: ForcePriority = ForcePriority.LOW,
    ) -> tuple[str, str | None]:
        # I don't think this should be called, but have to implement
        # because required abstract method
        # client_id = 0
        # self.on_actions_force(
        #     client_id,
        #     ActionsForceCommand(state, query, ephemeral_context, [action.name for action in actions]),
        # )
        raise NotImplementedError("Not implemented, should be handled in client class.")

    def add_context(  # noqa: D102
        self,
        game_title: str | None,
        message: str,
        reply_if_not_busy: bool,
    ) -> None:
        # I don't think this should be called, but have to implement
        # because required abstract method
        # client_id = 0
        # self.on_context(
        #     client_id,
        #     ContextCommand(message, not reply_if_not_busy),
        # )
        raise NotImplementedError("Not implemented, should be handled in client class.")

    def start(self, address: str, port: int) -> None:
        """Start hosting the websocket server with Trio in the background.

        Parameters
        ----------
        address : str
            The address to run the websocket server on.
        port : int
            The port to run the websocket server on. No other process should be using this port.

        Raises
        ------
        OSError
            If the specified port is already in use.

        """
        if self._received_loop_close_request:
            # Attempting to shut down
            self.log_critical("Something attempted to start websocket server during shutdown, ignoring.")
            return

        if self._async_library_running:
            # Already running, skip
            self.log_critical("Something attempted to start websocket server a 2nd time, ignoring.")
            return

        def done_callback(run_outcome: Outcome[None]) -> None:
            """Handle when trio run completes."""
            assert self._async_library_running, "How can stop running if not running?"
            self._async_library_running = False
            # Unwrap to make sure exceptions are printed
            try:
                run_outcome.unwrap()
            except Exception as exc:
                self.log_critical("".join(traceback.format_exception(exc)))
                raise

        self._async_library_running = True
        self._async_library_root_cancel = trio.CancelScope()

        async def root_run() -> None:
            """Root async run, wrapped with async_library_root_cancel so it's able to be stopped remotely."""
            with self._async_library_root_cancel:
                await self._run(address, port)

        try:
            # Start the Trio guest run
            trio.lowlevel.start_guest_run(
                root_run,
                done_callback=done_callback,
                run_sync_soon_threadsafe=self.run_sync_soon_threadsafe,
                host_uses_signal_set_wakeup_fd=False,
                restrict_keyboard_interrupt_to_checkpoints=True,
                strict_exception_groups=True,
            )
        except Exception as exc:
            # Make sure async_library_running can never be in invalid state
            # even if trio fails to launch for some reason (shouldn't happen but still)
            self._async_library_running = False
            self.log_critical(f"Failed to start async Trio guest run:\n{exc}")
            self.log_critical("".join(traceback.format_exception(exc)))
            raise

    def stop(self) -> None:
        """Stop hosting background websocket server."""
        if not self._async_library_running:
            return
        self._async_library_root_cancel.cancel()

    def on_close(self, shutdown_function: Callable[[], None]) -> None:
        """Gracefully handle application quit, cancel async run properly then call shutdown_function.

        This will stop the websocket server and then call `shutdown_function`.

        Parameters
        ----------
        shutdown_function : Callable[[], None]
            A function that will be called when the websocket server is stopped.

        """
        if self._received_loop_close_request:
            self.log_critical("Already closing, ignoring 2nd close request.")
            return

        self._received_loop_close_request = True

        # Already shut down, close
        if not self._async_library_running:
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
            if self._async_library_running:
                self.run_sync_soon_threadsafe(shutdown_then_call)
            else:
                # Finally shut down, call shutdown function
                shutdown_function()

        # Schedule `shutdown_function` to be called once trio run closes
        self.run_sync_soon_threadsafe(shutdown_then_call)

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
            self.log_critical("".join(traceback.format_exception(exc)))
            raise

    @property
    def clients_connected(self) -> int:
        """Number of clients connected."""
        return len(self._clients)

    async def _handle_websocket_request(
        self,
        request: WebSocketRequest,
    ) -> None:
        """Handle websocket connection request."""
        # With block means connection closed once scope has been left
        async with await request.accept() as connection:
            await self._handle_client_connection(connection)

    async def _handle_client_connection(
        self,
        connection: WebSocketConnection,
    ) -> None:
        """Handle websocket connection lifetime."""
        # Monotonically increasing client id so there will never be
        # duplicates
        client_id = self._next_client_id
        self._next_client_id += 1

        client = NeuroAPIClient(connection, self, client_id)

        # Channel buffer of zero means no buffer, receive_channel has to
        # be actively waiting for something to be sent for async partial
        # functions to go through
        send_channel, receive_channel = trio.open_memory_channel[
            "partial[Awaitable[Any]] | partial[Coroutine[Any, Any, Any]]"
        ](0)

        self._clients[client_id] = (client, send_channel)

        self.on_client_connect(client_id)

        try:
            with send_channel, receive_channel:
                async with trio.open_nursery() as nursery:
                    # Start running connection read and write tasks in
                    # the background
                    nursery.start_soon(
                        self._handle_consumer,
                        client,
                        nursery.cancel_scope,
                    )
                    nursery.start_soon(
                        self._handle_producer,
                        client,
                        receive_channel,
                    )
        except trio.Cancelled:
            self.log_info(f"Closing websocket connection for client id {client_id}.")
        finally:
            self.on_client_disconnect(client_id, client.game_title)
            del self._clients[client_id]

    async def _handle_consumer(
        self,
        client: NeuroAPIClient,
        cancel_scope: trio.CancelScope,
    ) -> None:
        """Handle websocket reading head."""
        while True:
            try:
                # Read from websocket and call message handlers
                await client.read_message()
            except ConnectionClosed:
                self.log_info("Websocket connection closed by client.")
                break
            except (TypeError, ValueError) as exc:
                self.log_error(str(exc))
                self.log_debug("".join(traceback.format_exception(exc)))
                traceback.print_exception(exc)
                self.log_debug("Assuming non-critical exception, keeping websocket open.")
            except Exception as exc:
                self.log_error(f"Error while reading/handling message: {exc}")
                self.log_error("".join(traceback.format_exception(exc)))
                traceback.print_exception(exc)
                self.log_error("Closing websocket connection due to error.")
                break
        # Cancel (stop) writing head
        cancel_scope.cancel()

    async def _handle_producer(
        self,
        client: NeuroAPIClient,
        receive_channel: trio.MemoryReceiveChannel[partial[Awaitable[Any]] | partial[Coroutine[Any, Any, Any]]],
    ) -> None:
        """Handle websocket writing head."""
        while True:
            # Wait for messages from sending side of memory channel (queue)
            async_partial = await receive_channel.receive()

            # Artificial latency
            # Make sure never < 0 or raises ValueError
            await trio.sleep(max(0, self.get_delay()))

            # Write message
            # If connection failure happens, will crash the read head
            # because exception is propagated and both share a nursery,
            # ensuring connection closes
            await async_partial()

    def _get_client(self, client_id: int) -> NeuroAPIClient | None:
        """Return NeuroAPIClient instance from given client id or None if not found."""
        result = self._clients.get(client_id)
        if result is None:
            self.log_error(f"No client with ID {client_id} connected.")
            return None
        client, _send_channel = result
        return client

    def _submit_async_action(
        self,
        client_id: int,
        async_partial: partial[Awaitable[Any]] | partial[Coroutine[Any, Any, Any]],
    ) -> bool:
        """Submit a message to the send queue. Return True if able to submit action successfully."""
        if not self.clients_connected:
            self.log_error("No clients connected!")
            return False
        _client, send_channel = self._clients[client_id]
        try:
            send_channel.send_nowait(async_partial)
        except trio.WouldBlock:
            self.log_error("Cannot send command to client, already trying to send a command.")
            return False
        return True

    def send_action(
        self,
        id_: str,
        name: str,
        data: str | None,
        client_id: int,
    ) -> bool:
        """Send an action command.

        Parameters
        ----------
        id_ : str
            An arbitrary unique string that identifies the action. This is used to match the action with the result returned by the game.

        """
        # Determine which clients to send to based on configuration
        clients: list[tuple[int, NeuroAPIClient]]
        if config().send_actions_to == SendActionsTo.ALL:
            clients = [(cid, client) for cid, (client, _) in self._clients.items()]
        elif config().send_actions_to == SendActionsTo.REGISTRANT:
            client = self._get_client(client_id)
            clients = [(client_id, client)] if client else []
        elif config().send_actions_to == SendActionsTo.FIRST_CONNECTED:
            first_client_id = min(self._clients.keys())
            client = self._get_client(first_client_id)
            clients = [(first_client_id, client)] if client else []
        elif config().send_actions_to == SendActionsTo.LAST_CONNECTED:
            last_client_id = max(self._clients.keys())
            client = self._get_client(last_client_id)
            clients = [(last_client_id, client)] if client else []
        else:
            self.log_error("Invalid send_actions_to configuration.")
            return False

        sent = False
        for cid, client in clients:
            if not self._submit_async_action(
                cid,
                partial(client.send_action_command, name, data),
            ):
                continue
            sent = True

            self.log_command(client_id, "action", False, name + (" {...}" if data else ""))

        # Return true if sent to at least one client
        return sent

    def send_actions_reregister_all(
        self,
        client_id: int | None,
    ) -> bool:
        """Send an [actions/reregister_all](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md#reregister-all-actions) command.

        This signals to the game to unregister all actions and reregister them.

        Returns
        -------
        bool
            `True` if the command was sent successfully, `False` otherwise.

        Warnings
        --------
        This command is part of the proposed API and is not officially supported yet.
        Some SDKs may not support it.

        """
        client_ids = [client_id] if client_id is not None else list(self._clients.keys())
        result = True

        for client_id in client_ids:
            client = self._get_client(client_id)

            if client is None:
                result = False
                continue

            if not self._submit_async_action(
                client_id,
                partial(client.send_reregister_all_command),
            ):
                result = False
                continue

            self.log_command(client_id, "actions/reregister_all", False)

        self.log_info("actions/reregister_all is a proposed feature and may not be supported.")
        return result

    def send_shutdown_graceful(
        self,
        wants_shutdown: bool,
        client_id: int | None,
    ) -> bool:
        """Send a [shutdown/graceful](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md#graceful-shutdown) command.

        What this command does depends on the `wants_shutdown` parameter.

        Parameters
        ----------
        wants_shutdown : bool
            If `True`, the game should prepare for shutdown. If `False`, the game should cancel any pending graceful
            shutdown.

        Returns
        -------
        bool
            `True` if the command was sent successfully, `False` otherwise.

        Warnings
        --------
        This command is part of the proposed API and is not officially supported yet.
        Some SDKs may not support it.

        """
        client_ids = [client_id] if client_id is not None else list(self._clients.keys())
        result = True
        for client_id in client_ids:
            client = self._get_client(client_id)

            if client is None:
                result = False
                continue

            if not self._submit_async_action(
                client_id,
                partial(client.send_graceful_shutdown_command, wants_shutdown),
            ):
                result = False
                continue

            self.log_command(client_id, "shutdown/graceful", False, f"{wants_shutdown=}")

        self.log_info("shutdown/graceful is a proposed feature and may not be supported.")
        return result

    def send_shutdown_immediate(
        self,
        client_id: int | None,
    ) -> bool:
        """Send a [shutdown/immediate](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md#immediate-shutdown) command.

        This signals to the game that it will be shut down within a few seconds.

        Returns
        -------
        bool
            `True` if the command was sent successfully, `False` otherwise.

        Warnings
        --------
        This command is part of the proposed API and is not officially supported yet.
        Some SDKs may not support it.

        """
        client_ids = [client_id] if client_id is not None else list(self._clients.keys())
        result = True
        for client_id in client_ids:
            client = self._get_client(client_id)

            if client is None:
                result = False
                continue

            if not self._submit_async_action(
                client_id,
                partial(client.send_immediate_shutdown_command),
            ):
                result = False
                continue

            self.log_command(client_id, "shutdown/immediate", False)

        self.log_info("shutdown/immediate is a proposed feature and may not be supported.")
        return result


class StartupCommand(NamedTuple):
    """[`startup`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#startup) command."""

    game: str
    """The name of the game."""


class ContextCommand(NamedTuple):
    """[`context`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#context) command."""

    message: str
    """The context message."""
    silent: bool
    """If `True`, Neuro should not directly react to the message."""


class ActionsRegisterCommand:
    """[`actions/register`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#register-actions) command."""

    __slots__ = ("actions",)

    def __init__(self, client_id: int, game: str, actions: list[ActionSchema]) -> None:
        """Initialize actions register command."""
        # 'schema' may be omitted, so get() is used
        self.actions = [
            NeuroAction(action["name"], action["description"], action.get("schema"), client_id, game)
            for action in actions
        ]
        """The list of actions to register."""


class ActionsUnregisterCommand(NamedTuple):
    """[`actions/unregister`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#unregister-actions) command."""

    action_names: list[str]
    """The list of action names to unregister."""


class ActionsForceCommand(NamedTuple):
    """[`actions/force`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#force-actions) command."""

    state: str | None
    """The state of the action."""
    query: str
    """The query string."""
    ephemeral_context: bool
    action_names: list[str]
    priority: ForcePriority


class ActionResultCommand(NamedTuple):
    """[`action/result`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#action-result) command."""

    success: bool
    message: str | None


class ShutdownReadyCommand:
    """[`shutdown/ready`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md#shutdown-ready) command."""

    __slots__ = ()
