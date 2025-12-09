from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import trio

if sys.version_info < (3, 11):
    pass

from collections.abc import Coroutine
from functools import partial

from neuro_api_tony.api import ActionsRegisterCommand, NeuroAPI
from neuro_api_tony.model import NeuroAction

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from neuro_api.server import ActionSchema


@pytest.fixture
def api() -> NeuroAPI:
    """Create a NeuroAPI instance for testing."""
    return NeuroAPI(Mock())


@pytest.fixture(autouse=True)
def print_exception_to_raise() -> Generator[None, None, None]:
    """Make traceback.print_exception raise exception instead of printing it."""

    def raise_(exc: BaseException) -> None:
        raise exc from None

    with patch(
        "traceback.print_exception",
        raise_,
    ):
        yield None


def test_start(api: NeuroAPI) -> None:
    """Test starting the WebSocket server."""
    with patch(
        "trio.lowlevel.start_guest_run",
        new_callable=Mock,
    ) as mock_start:
        api.start("localhost", 8080)
        assert api._async_library_running

        # Attempt to start again
        api.start("localhost", 8080)

        # Ensure start only called once
        assert mock_start.call_count == 1


def test_run_start_stop(api: NeuroAPI) -> None:
    """Test starting and stopping the WebSocket server."""
    tasks: list[Callable[[], None]] = []

    def run_sync_soon_threadsafe(func: Callable[[], None]) -> None:
        tasks.append(func)

    def run_tasks_until_empty() -> None:
        # Limit to 100 iterations
        for _ in range(100):
            if not tasks:
                break
            tasks.pop(0)()

    with patch.object(
        api,
        "run_sync_soon_threadsafe",
        run_sync_soon_threadsafe,
    ):
        api.start("localhost", 8080)

    assert api._async_library_running
    api.stop()

    # 2nd cancel shouldn't lead to any problems
    api.stop()

    assert api._async_library_running

    close_mock = Mock()
    with patch.object(
        api,
        "run_sync_soon_threadsafe",
        run_sync_soon_threadsafe,
    ):
        api.on_close(close_mock)

        # 2nd start should be ignored while shutting down
        api.start("localhost", 8080)

        # 2nd close handle should be skipped
        api.on_close(close_mock)

        run_tasks_until_empty()

    close_mock.assert_called_once()

    assert not api._async_library_running
    # Make sure stop when not running is also fine
    api.stop()  # type: ignore[unreachable]


def test_run_start_failure(api: NeuroAPI) -> None:
    """Test that async_library_running is handled even if guest run start fails."""

    def start_guest_run(*args: Any, **kwargs: Any) -> None:
        raise ValueError("jerald")

    with pytest.raises(ValueError, match=r"^jerald$"):
        with patch(
            "trio.lowlevel.start_guest_run",
            start_guest_run,
        ):
            api.start("localhost", 8080)
    assert not api._async_library_running


##@pytest.mark.trio
##async def test_handle_websocket_request_reject(api: NeuroAPI) -> None:
##    """Test rejecting a WebSocket connection request when already connected."""
##    send, receive = trio.open_memory_channel[str](0)
##    api._message_send_channel = send
##    mock_request = MagicMock()
##    mock_request.reject = AsyncMock()
##
##    await api._handle_websocket_request(mock_request)
##
##    mock_request.reject.assert_called_once_with(
##        503,
##        body=b"Server does not support multiple connections at once currently",
##    )


##def test_send_action(api: NeuroAPI) -> None:
##    """Test sending an action command."""
##    send, receive = trio.open_memory_channel[str](1)
##    api._message_send_channel = send
##    assert api.send_action("123", "test_action", None)
##
##    assert api._current_action_id == "123"


##def test_send_action_with_data(api: NeuroAPI) -> None:
##    """Test sending an action command."""
##    send, receive = trio.open_memory_channel[str](1)
##    api._message_send_channel = send
##    assert api.send_action("123", "test_action", "data field")
##
##    assert api._current_action_id == "123"
##    assert (
##        receive.receive_nowait()
##        == '{"command": "action", "data": {"id": "123", "name": "test_action", "data": "data field"}}'
##    )


##def test_send_actions_reregister_all(api: NeuroAPI) -> None:
##    """Test sending reregister all command."""
##    send, receive = trio.open_memory_channel[str](1)
##    api._message_send_channel = send
##    assert api.send_actions_reregister_all()
##
##    assert receive.receive_nowait() == '{"command": "actions/reregister_all"}'


##def test_send_actions_reregister_all_not_connected(api: NeuroAPI) -> None:
##    """Test sending reregister all command but not connected."""
##    assert not api.send_actions_reregister_all()


##def test_send_shutdown_graceful(api: NeuroAPI) -> None:
##    """Test sending graceful shutdown command."""
##    send, receive = trio.open_memory_channel[str](1)
##    api._message_send_channel = send
##    assert api.send_shutdown_graceful(True)
##
##    assert receive.receive_nowait() == '{"command": "shutdown/graceful", "data": {"wants_shutdown": true}}'


##def test_send_shutdown_graceful_not_connected(api: NeuroAPI) -> None:
##    """Test sending graceful shutdown command."""
##    assert not api.send_shutdown_graceful(True)


##def test_send_shutdown_immediate(api: NeuroAPI) -> None:
##    """Test sending immediate shutdown command."""
##    send, receive = trio.open_memory_channel[str](1)
##    api._message_send_channel = send
##    assert api.send_shutdown_immediate()
##
##    assert receive.receive_nowait() == '{"command": "shutdown/immediate"}'


##def test_send_shutdown_immediate_not_connected(api: NeuroAPI) -> None:
##    """Test sending immediate shutdown command but not connected."""
##    assert not api.send_shutdown_immediate()


##def test_send_action_no_client(api: NeuroAPI) -> None:
##    """Test sending an action command when no client is connected."""
##    assert not api.send_action("123", "test_action", None)
##
##    assert api._current_action_id is None


##def test_check_invalid_keys_recursive(api: NeuroAPI) -> None:
##    """Test checking for invalid keys in a schema."""
##    schema = {
##        "valid_key": {},
##        "allOf": {},
##        "another_key": {
##            "$vocabulary": {},
##            "3rd level": [
##                {
##                    "additionalProperties": "seven",
##                    "uses_waffle_iron": True,
##                },
##                "spaghetti",
##            ],
##        },
##    }
##    invalid_keys = api.check_invalid_keys_recursive(schema)
##
##    assert invalid_keys == ["allOf", "$vocabulary", "additionalProperties"]


##def test_check_invalid_keys_recursive_unhandled(api: NeuroAPI) -> None:
##    """Test checking for invalid keys in a schema."""
##    schema = {
##        "valid_key": set(),
##        "writeOnly": True,
##    }
##    api.log_error = Mock()
##
##    invalid = api.check_invalid_keys_recursive(schema)
##    assert invalid == ["writeOnly"]
##    api.log_error.assert_called_once_with("Unhandled schema value type <class 'set'> (set())")


def test_actions_register_command() -> None:
    actions: list[ActionSchema] = [
        {
            "name": "jerald",
            "description": "jerald action",
        },
        {
            "name": "jerald_schema",
            "description": "jerald action with schema",
            "schema": {},
        },
    ]

    command = ActionsRegisterCommand(0, "test_game", actions)
    assert command.actions == [
        NeuroAction("jerald", "jerald action", None, 0, "test_game"),
        NeuroAction("jerald_schema", "jerald action with schema", {}, 0, "test_game"),
    ]


##@pytest.mark.trio
##async def test_handle_websocket_request_accept(api: NeuroAPI) -> None:
##    """Test handling a WebSocket connection request."""
##    send, receive = trio.open_memory_channel[str](1)
##
##    class Websocket:
##        get_message = receive.receive
##        send_message = send.send
##
##    class Request(WebSocketRequest):
##        def __init__(self) -> None:
##            pass
##
##        async def accept(  # type: ignore[override]
##            self,
##            *,
##            subprotocol: str | None = None,
##            extra_headers: list[tuple[bytes, bytes]] | None = None,
##        ) -> AbstractAsyncContextManager[Websocket]:
##            @asynccontextmanager
##            async def manager() -> AsyncGenerator[Websocket, None]:
##                yield Websocket()
##
##            return manager()
##
##    request = Request()
##
##    async with trio.open_nursery() as nursery:
##        nursery.start_soon(api._handle_websocket_request, request)
##        await trio.sleep(0.05)
##        nursery.cancel_scope.cancel()
##
##    assert api._message_send_channel is None


##@pytest.mark.trio
##async def test_handle_client_connection(api: NeuroAPI) -> None:
##    """Test handling a client connection."""
##    mock_websocket = MagicMock()
##    send, receive = trio.open_memory_channel[str](1)
##    ws_send, ws_receive = trio.open_memory_channel[str](1)
##    mock_websocket.get_message = ws_receive.receive
##    mock_websocket.send_message = ws_send.send
##    api._message_send_channel = send
##
##    await send.send('{"command": "startup", "game": "test_game"}')
##
##    async with trio.open_nursery() as nursery:
##        nursery.start_soon(
##            api._handle_client_connection,
##            mock_websocket,
##            receive,
##        )
##        await trio.sleep(0.05)
##        nursery.cancel_scope.cancel()


##@pytest.mark.trio
##async def test_handle_consumer(api: NeuroAPI) -> None:
##    """Test handling a consumer message."""
##    mock_websocket = MagicMock()
##    send, receive = trio.open_memory_channel[str](1)
##    mock_websocket.get_message = receive.receive
##    api._message_send_channel = send
##
##    await send.send('{"command": "startup", "game": "test_game"}')
##
##    async with trio.open_nursery() as nursery:
##        cancel_scope = trio.CancelScope()
##        nursery.start_soon(api._handle_consumer, mock_websocket, cancel_scope)
##        await trio.sleep(0.05)
##        cancel_scope.cancel()
##        nursery.cancel_scope.cancel()
##
##    assert api._current_game == "test_game"


##@pytest.mark.trio
##async def test_handle_consumer_invalid_json(api: NeuroAPI) -> None:
##    """Test handling an invalid JSON message."""
##    mock_websocket = MagicMock()
##    send, receive = trio.open_memory_channel[str](1)
##    mock_websocket.get_message = receive.receive
##    api._message_send_channel = send
##
##    # Missing closing brace
##    await send.send('{"command": "startup", "game": "test_game"')
##
##    had_json_error = False
##
##    def handle_json_error(
##        multi_exc: BaseExceptionGroup[JSONDecodeError],
##    ) -> None:
##        nonlocal had_json_error
##        exc = multi_exc.args[1][0]
##        assert exc.args[0] == "Expecting ',' delimiter: line 1 column 43 (char 42)"
##        had_json_error = True
##
##    with catch(
##        {
##            JSONDecodeError: handle_json_error,
##        },
##    ):
##        async with trio.open_nursery() as nursery:
##            cancel_scope = trio.CancelScope()
##            nursery.start_soon(
##                api._handle_consumer,
##                mock_websocket,
##                cancel_scope,
##            )
##            await trio.sleep(0.05)
##            cancel_scope.cancel()
##            nursery.cancel_scope.cancel()
##
##    if not had_json_error:
##        raise ValueError("Should have gotten JSONDecodeError")
##
##    assert api._current_game == ""


##@pytest.mark.trio
##async def test_handle_producer(api: NeuroAPI) -> None:
##    """Test handling a producer message."""
##    mock_websocket = MagicMock()
##    send, receive = trio.open_memory_channel[str](1)
##    mock_websocket.send_message = AsyncMock(return_value=None)
##    api._message_send_channel = send
##
##    send.send_nowait('{"command": "action", "data": {"id": "123", "name": "test_action"}}')
##
##    async with trio.open_nursery() as nursery:
##        nursery.start_soon(api._handle_producer, mock_websocket, receive)
##        await trio.sleep(0.05)
##        nursery.cancel_scope.cancel()
##
##    mock_websocket.send_message.assert_called_once_with(
##        '{"command": "action", "data": {"id": "123", "name": "test_action"}}',
##    )


@pytest.mark.trio
async def test_handle_producer_no_client(api: NeuroAPI) -> None:
    """Test handling a producer message when no client is connected."""
    _send, receive = trio.open_memory_channel[partial[Coroutine[Any, Any, Any]]](1)

    async with trio.open_nursery() as nursery:
        nursery.start_soon(api._handle_producer, MagicMock(), receive)
        await trio.sleep(0.05)
        nursery.cancel_scope.cancel()


##@pytest.mark.trio
##async def test_handle_consumer_unexpected_command(api: NeuroAPI) -> None:
##    """Test handling an unexpected command in the consumer."""
##    mock_websocket = MagicMock()
##    send, receive = trio.open_memory_channel[str](1)
##    mock_websocket.get_message = receive.receive
##    api._message_send_channel = send
##
##    await send.send('{"command": "unknown_command"}')
##
##    api.log_warning = Mock()
##
##    async with trio.open_nursery() as nursery:
##        cancel_scope = trio.CancelScope()
##        nursery.start_soon(api._handle_consumer, mock_websocket, cancel_scope)
##        await trio.sleep(0.05)
##        cancel_scope.cancel()
##        nursery.cancel_scope.cancel()
##
##    api.log_warning.assert_called_with("Unknown command: unknown_command")


##@pytest.mark.trio
##async def test_handle_consumer_action_result(api: NeuroAPI) -> None:
##    """Test handling an action/result command in the consumer."""
##    mock_websocket = MagicMock()
##    send, receive = trio.open_memory_channel[str](1)
##    mock_websocket.get_message = receive.receive
##    api._message_send_channel = send
##
##    await send.send('{"command": "action/result", "data": {"id": "123", "success": true}}')
##
##    async with trio.open_nursery() as nursery:
##        cancel_scope = trio.CancelScope()
##        nursery.start_soon(api._handle_consumer, mock_websocket, cancel_scope)
##        await trio.sleep(0.05)
##        cancel_scope.cancel()
##        nursery.cancel_scope.cancel()
##
##    assert api._current_action_id is None
