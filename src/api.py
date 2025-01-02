import asyncio
from threading import Thread, Lock
from typing import Any, Callable

import jsonschema
import jsonschema.exceptions
from .model import NeuroAction
import json

from websockets.asyncio.server import serve, ServerConnection

ACTION_NAME_ALLOWED_CHARS = 'abcdefghijklmnopqrstuvwxyz0123456789_-'

# See https://github.com/VedalAI/neuro-game-sdk/blob/main/API/SPECIFICATION.md#action
INVALID_SCHEMA_KEYS = ["$anchor", "$comment", "$defs", "$dynamicAnchor", "$dynamicRef", "$id", "$ref", "$schema", "$vocabulary", "additionalProperties", "allOf", "anyOf", "contentEncoding", "contentMediaType", "contentSchema", "dependentRequired", "dependentSchemas", "deprecated", "description", "else", "if", "maxProperties", "minProperties", "not", "oneOf", "patternProperties", "readOnly", "then", "title", "unevaluatedItems", "unevaluatedProperties", "writeOnly"]

class NeuroAPI:

    def __init__(self):
        self.thread = None

        self.message_queue = asyncio.Queue()
        self.queue_lock = Lock() # threading, not asyncio
        self.current_game = ''
        self.current_action_id: str | None = None

        # Dependency injection
        self.on_startup: Callable[[StartupCommand], None] = lambda cmd: None
        self.on_context: Callable[[ContextCommand], None] = lambda cmd: None
        self.on_actions_register: Callable[[ActionsRegisterCommand], None] = lambda cmd: None
        self.on_actions_unregister: Callable[[ActionsUnregisterCommand], None] = lambda cmd: None
        self.on_actions_force: Callable[[ActionsForceCommand], None] = lambda cmd: None
        self.on_action_result: Callable[[ActionResultCommand], None] = lambda cmd: None
        self.on_shutdown_ready: Callable[[ShutdownReadyCommand], None] = lambda cmd: None
        self.on_unknown_command: Callable[[Any], None] = lambda cmd: None
        self.log_system: Callable[[str], None] = lambda message: None
        self.log_debug: Callable[[str], None] = lambda message: None
        self.log_info: Callable[[str], None] = lambda message: None
        self.log_warning: Callable[[str], None] = lambda message: None
        self.log_error: Callable[[str], None] = lambda message: None
        self.log_raw: Callable[[str, bool], None] = lambda message: None
        self.get_delay: Callable[[], float] = lambda: -1

    def start(self, address: str, port: int):
        '''Start the websocket thread.'''

        if self.thread is not None:
            return
        
        self.thread = Thread(target=self.__start_thread, args=[address, port], daemon=True, name='API Thread')
        self.thread.start()

    def __start_thread(self, address: str, port: int):
        '''Start the websocket thread.'''

        asyncio.run(self.__run(address, port))

    async def __run(self, address: str, port: int):
        async with serve(self.__handle_message, address, port) as server:
            self.log_system('Websocket server started on ws://' + address + ':' + str(port) + '.')
            await server.serve_forever()
        
    # http://web.archive.org/web/20190623114747/https://websockets.readthedocs.io/en/stable/intro.html#both
    async def __handle_message(self, websocket: ServerConnection):
        consumer_task = asyncio.ensure_future(self.__handle_consumer(websocket))
        producer_task = asyncio.ensure_future(self.__handle_producer(websocket))

        done, pending = await asyncio.wait([consumer_task, producer_task], return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

    async def __handle_consumer(self, websocket: ServerConnection):
        async for message in websocket:
            try:
                json_cmd = json.loads(message)
                self.log_raw(json.dumps(json_cmd, indent=2), True)

                game = json_cmd.get('game', {})
                data = json_cmd.get('data', {})

                if game == '' or not isinstance(game, str):
                    self.log_warning('Game name is not set.')
                else:
                    # Check game name
                    if json_cmd['command'] == 'startup' or json_cmd['command'] == 'game/startup':
                        self.current_game = game
                    elif self.current_game != game:
                        self.log_warning('Game name does not match the current game.')
                    elif self.current_game == '':
                        self.log_warning('No startup command received.')

                # Check action result when waiting for it
                if self.current_action_id is not None and json_cmd['command'] == 'actions/force':
                    self.log_warning(f'Received actions/force while waiting for action/result.')

                self.log_system(f'Command received: {json_cmd["command"]}')

                # Handle the command
                match json_cmd['command']:
                    case 'startup' | 'game/startup':
                        self.current_action_id = None

                        self.on_startup(StartupCommand())

                        if json_cmd['command'] == 'game/startup':
                            self.log_warning('"game/startup" command is deprecated. Use "startup" instead.')

                    case 'context':
                        self.on_context(ContextCommand(data['message'], data['silent']))

                    case 'actions/register':
                        # Check the actions
                        for action in data['actions']:
                            # Check the schema
                            if 'schema' in action:
                                try:
                                    jsonschema.Draft7Validator.check_schema(action['schema'])
                                except jsonschema.exceptions.SchemaError as e:
                                    self.log_error(f'Invalid schema for action "{action["name"]}": {e}')
                                    continue

                                invalid_keys = self.check_invalid_keys_recursive(action['schema'])

                                if len(invalid_keys) > 0:
                                    self.log_warning(f'Disallowed keys in schema: {", ".join(invalid_keys)}')

                            # Check the name
                            if not isinstance(action['name'], str):
                                self.log_error(f'Action name is not a string: {action["name"]}')
                                continue

                            if not all(c in ACTION_NAME_ALLOWED_CHARS for c in action['name']):
                                self.log_warning(f'Action name is not a lowercase string.')

                            if action['name'] == '':
                                self.log_warning('Action name is empty.')
                            
                        self.on_actions_register(ActionsRegisterCommand(data['actions']))
                    
                    case 'actions/unregister':
                        self.on_actions_unregister(ActionsUnregisterCommand(data['action_names']))

                    case 'actions/force':
                        self.on_actions_force(ActionsForceCommand(data.get('state'), data['query'], data.get('ephemeral_context', False), data['action_names']))
                    
                    case 'action/result':
                        # Check if an action/result was expected
                        if self.current_action_id is None:
                            self.log_warning('Unexpected action/result.')
                        # Check if the action ID matches
                        elif self.current_action_id != data['id']:
                            self.log_warning(f'Received action ID "{data["id"]}" does not match the expected action ID "{self.current_action_id}".')

                        self.log_debug(f'Action ID: {data["id"]}')

                        self.current_action_id = None
                        self.on_action_result(ActionResultCommand(data['success'], data.get('message', None)))

                    case 'shutdown/ready':
                        self.log_warning('This command is not officially supported.')
                        self.on_shutdown_ready(ShutdownReadyCommand())

                    case _:
                        self.log_warning('Unknown command.')
                        self.on_unknown_command(json_cmd)

            except Exception as e:
                self.log_error(f'Error while handling message: {e}')

    async def __handle_producer(self, websocket: ServerConnection):
        while True:
            await asyncio.sleep(0.1)

            message: str
            with self.queue_lock:
                if self.message_queue.empty():
                    continue

                message = await self.message_queue.get()

            await asyncio.sleep(self.get_delay())

            await websocket.send(message)

            try:
                self.log_raw(json.dumps(json.loads(message), indent=2), False)
            except:
                self.log_raw(message, False)

    def send_action(self, id: str, name: str, data: str | None):
        '''Send an action command.'''

        obj = {
            'command': 'action',
            'data': {
                'id': id,
                'name': name
            }
        }

        if data is not None:
            obj['data']['data'] = data

        message = json.dumps(obj)

        with self.queue_lock:
            self.message_queue.put_nowait(message)
        self.current_action_id = id
        self.log_system('Command sent: action')
        self.log_debug(f'Action ID: {id}')

    def send_actions_reregister_all(self):
        '''Send an actions/reregister_all command.'''

        message = json.dumps({
            'command': 'actions/reregister_all'
        })

        with self.queue_lock:
            self.message_queue.put_nowait(message)
        self.log_system('Command sent: actions/reregister_all')
        self.log_warning('This command is not officially supported.')

    def send_shutdown_graceful(self, wants_shutdown: bool):
        '''Send a shutdown/graceful command.'''

        message = json.dumps({
            'command': 'shutdown/graceful',
            'data': {
                'wants_shutdown': wants_shutdown
            }
        })

        with self.queue_lock:
            self.message_queue.put_nowait(message)
        self.log_system('Command sent: shutdown/graceful')
        self.log_warning('This command is not officially supported.')

    def send_shutdown_immediate(self):
        '''Send a shutdown/immediate command.'''

        message = json.dumps({
            'command': 'shutdown/immediate'
        })

        with self.queue_lock:
            self.message_queue.put_nowait(message)
        self.log_system('Command sent: shutdown/immediate')
        self.log_warning('This command is not officially supported.')
        
    def check_invalid_keys_recursive(self, sub_schema: dict[str, Any]) -> list[str]:
        '''
        Recursively checks for invalid keys in the schema.
        Returns a list of invalid keys that were found.
        '''

        invalid_keys = []

        for key, value in sub_schema.items():
            if key in INVALID_SCHEMA_KEYS:
                invalid_keys.append(key)
            elif isinstance(value, dict):
                invalid_keys.extend(self.check_invalid_keys_recursive(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        invalid_keys.extend(self.check_invalid_keys_recursive(item))
        
        return invalid_keys

class StartupCommand:

    def __init__(self):
        pass # No data needed

class ContextCommand:

    def __init__(self, message: str, silent: bool):
        self.message = message
        self.silent = silent

class ActionsRegisterCommand:
    
    def __init__(self, actions: list[Any]):
        # 'schema' may be omitted, so get() is used
        self.actions = [NeuroAction(action['name'], action['description'], action.get('schema')) for action in actions]

class ActionsUnregisterCommand:
    
    def __init__(self, action_names: list[str]):
        self.action_names = action_names

class ActionsForceCommand:
    
    def __init__(self, state: str | None, query: str, ephemeral_context: bool, action_names: list[str]):
        self.state = state
        self.query = query
        self.ephemeral_context = ephemeral_context
        self.action_names = action_names

class ActionResultCommand:
    
    def __init__(self, success: bool, message: str | None):
        self.success = success
        self.message = message

class ShutdownReadyCommand:

    def __init__(self):
        pass # No data needed