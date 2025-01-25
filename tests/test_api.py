from __future__ import annotations

import pytest
import trio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from neuro_api_tony.api import NeuroAPI, ActionsRegisterCommand
from neuro_api_tony.model import NeuroAction
from collections.abc import Callable


@pytest.fixture
def api() -> NeuroAPI:
    """Create a NeuroAPI instance for testing."""
    return NeuroAPI()


def test_start(api: NeuroAPI) -> None:
    """Test starting the WebSocket server."""
    with patch(
        "trio.lowlevel.start_guest_run",
        new_callable=Mock,
    ) as mock_start:
        api.start("localhost", 8080)
        assert api.async_library_running

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

    with patch(
        "wx.CallAfter",
        run_sync_soon_threadsafe,
    ):
        api.start("localhost", 8080)

    assert api.async_library_running
    api.stop()

    # 2nd cancel shouldn't lead to any problems
    api.stop()

    assert api.async_library_running

    close_mock = Mock()
    with patch(
        "wx.CallAfter",
        run_sync_soon_threadsafe,
    ):
        api.on_close(close_mock)

        # 2nd start should be ignored while shutting down
        api.start("localhost", 8080)

        # 2nd close handle should be skipped
        api.on_close(close_mock)

        run_tasks_until_empty()

    close_mock.assert_called_once()

    assert not api.async_library_running
    # Make sure stop when not running is also fine
    api.stop()


def test_run_start_failure(api: NeuroAPI) -> None:
    """Test that async_library_running is handled even if guest run start fails."""
    def start_guest_run(*args: Any, **kwargs: Any) -> None:
        raise ValueError("jerald")

    with pytest.raises(ValueError, match="^jerald$"):
        with patch(
            "trio.lowlevel.start_guest_run",
            start_guest_run,
        ):
            api.start("localhost", 8080)
    assert not api.async_library_running


@pytest.mark.trio
async def test_handle_websocket_request_reject(api: NeuroAPI) -> None:
    """Test rejecting a WebSocket connection request when already connected."""
    send, receive = trio.open_memory_channel[str](0)
    api.message_send_channel = send
    mock_request = MagicMock()
    mock_request.reject = AsyncMock()

    await api._handle_websocket_request(mock_request)

    mock_request.reject.assert_called_once_with(
        503,
        body=b"Server does not support multiple connections at once currently",
    )


def test_send_action(api: NeuroAPI) -> None:
    """Test sending an action command."""
    send, receive = trio.open_memory_channel[str](1)
    api.message_send_channel = send
    assert api.send_action("123", "test_action", None)

    assert api.current_action_id == "123"
    assert receive.receive_nowait() == '{"command": "action", "data": {"id": "123", "name": "test_action", "data": null}}'


def test_send_actions_reregister_all(api: NeuroAPI) -> None:
    """Test sending reregister all command."""
    send, receive = trio.open_memory_channel[str](1)
    api.message_send_channel = send
    assert api.send_actions_reregister_all()

    assert receive.receive_nowait() == '{"command": "actions/reregister_all"}'


def test_send_actions_reregister_all_not_connected(api: NeuroAPI) -> None:
    """Test sending reregister all command but not connected."""
    assert not api.send_actions_reregister_all()


def test_send_shutdown_graceful(api: NeuroAPI) -> None:
    """Test sending graceful shutdown command."""
    send, receive = trio.open_memory_channel[str](1)
    api.message_send_channel = send
    assert api.send_shutdown_graceful(True)

    assert receive.receive_nowait() == '{"command": "shutdown/graceful", "data": {"wants_shutdown": true}}'


def test_send_shutdown_graceful_not_connected(api: NeuroAPI) -> None:
    """Test sending graceful shutdown command."""
    assert not api.send_shutdown_graceful(True)


def test_send_shutdown_immediate(api: NeuroAPI) -> None:
    """Test sending immediate shutdown command."""
    send, receive = trio.open_memory_channel[str](1)
    api.message_send_channel = send
    assert api.send_shutdown_immediate()

    assert receive.receive_nowait() == '{"command": "shutdown/immediate"}'

def test_send_shutdown_immediate_not_connected(api: NeuroAPI) -> None:
    """Test sending immediate shutdown command but not connected."""
    assert not api.send_shutdown_immediate()


def test_send_action_no_client(api: NeuroAPI) -> None:
    """Test sending an action command when no client is connected."""
    assert not api.send_action("123", "test_action", None)

    assert api.current_action_id is None


def test_check_invalid_keys_recursive(api: NeuroAPI) -> None:
    """Test checking for invalid keys in a schema."""
    schema = {
        "valid_key": {},
        "allOf": {},
        "another_key": {
            "$vocabulary": {},
            "3rd level": [
                {
                    "additionalProperties": "seven",
                    "uses_waffle_iron": True,
                },
                "spaghetti",
            ]
        },
    }
    invalid_keys = api.check_invalid_keys_recursive(schema)

    assert invalid_keys == ['allOf', '$vocabulary', 'additionalProperties']


def test_check_invalid_keys_recursive_unhandled(api: NeuroAPI) -> None:
    """Test checking for invalid keys in a schema."""
    schema = {
        "valid_key": set(),
        "writeOnly": True,
    }
    api.log_error = Mock()

    invalid = api.check_invalid_keys_recursive(schema)
    assert invalid == ["writeOnly"]
    api.log_error.assert_called_once_with(
        "Unhandled schema value type <class 'set'> (set())"
    )

def test_actions_register_command() -> None:
    actions = [
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

    command = ActionsRegisterCommand(actions)
    assert command.actions == [
        NeuroAction("jerald", "jerald action", None),
        NeuroAction("jerald_schema", "jerald action with schema", {}),
    ]
