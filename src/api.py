import asyncio
from threading import Thread
from typing import Any, Callable

import jsonschema
from .model import NeuroAction
import json

from websockets.asyncio.server import serve

class NeuroAPI:

    def __init__(self):
        self.thread = None

        self.message_queue = asyncio.Queue()

        # Dependency injection
        self.on_startup: Callable[[StartupCommand], None] = lambda cmd: None
        self.on_context: Callable[[ContextCommand], None] = lambda cmd: None
        self.on_actions_register: Callable[[ActionsRegisterCommand], None] = lambda cmd: None
        self.on_actions_unregister: Callable[[ActionsUnregisterCommand], None] = lambda cmd: None
        self.on_actions_force: Callable[[ActionsForceCommand], None] = lambda cmd: None
        self.on_action_result: Callable[[ActionResultCommand], None] = lambda cmd: None
        self.on_shutdown_ready: Callable[[ShutdownReadyCommand], None] = lambda cmd: None
        self.on_unknown_command: Callable[[Any], None] = lambda cmd: None
        self.log: Callable[[str], None] = lambda message: None
        self.log_network: Callable[[str, bool], None] = lambda message: None

    def start(self):
        '''Start the websocket thread.'''

        if self.thread is not None:
            return
        
        self.thread = Thread(target=self.__start_thread, daemon=True, name='API Thread')
        self.thread.start()

    def __start_thread(self):
        '''Start the websocket thread.'''

        asyncio.run(self.__run())

    async def __run(self):
        async with serve(self.__handle_message, 'localhost', 8000) as server:
            self.log('Websocket started.')
            await server.serve_forever()
        
    # http://web.archive.org/web/20190623114747/https://websockets.readthedocs.io/en/stable/intro.html#both
    async def __handle_message(self, websocket):
        consumer_task = asyncio.ensure_future(self.__handle_consumer(websocket))
        producer_task = asyncio.ensure_future(self.__handle_producer(websocket))

        done, pending = await asyncio.wait([consumer_task, producer_task], return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

    async def __handle_consumer(self, websocket):
        async for message in websocket:
            try:
                json_cmd = json.loads(message)
                data = json_cmd.get('data', {})

                self.log_network(json.dumps(json_cmd, indent=2), True)

                match json_cmd['command']:
                    case 'startup' | 'game/startup':
                        self.on_startup(StartupCommand())

                    case 'context':
                        self.on_context(ContextCommand(data['message'], data['silent']))

                    case 'actions/register':
                        self.on_actions_register(ActionsRegisterCommand(data['actions']))
                    
                    case 'actions/unregister':
                        self.on_actions_unregister(ActionsUnregisterCommand(data['action_names']))

                    case 'actions/force':
                        self.on_actions_force(ActionsForceCommand(data['state'], data['query'], data.get('ephemeral_context', False), data['action_names']))
                    
                    case 'action/result':
                        self.on_action_result(ActionResultCommand(data['success'], data.get('message', None)))

                    case 'shutdown/ready':
                        self.on_shutdown_ready(ShutdownReadyCommand())

                    case _:
                        self.on_unknown_command(json_cmd)

            except Exception as e:
                self.log(f'Error: {e}\nWhile handling message:\n{message}')

    async def __handle_producer(self, websocket):
        while True:
            if self.message_queue.empty():
                await asyncio.sleep(0.1)
                continue

            message = await self.message_queue.get()
            await websocket.send(message)

            try:
                self.log_network(json.dumps(json.loads(message), indent=2), False)
            except:
                self.log_network(message, False)

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

        self.message_queue.put_nowait(message)

    def send_actions_reregister_all(self):
        '''Send an actions/reregister_all command.'''

        message = json.dumps({
            'command': 'actions/reregister_all'
        })

    def send_shutdown_graceful(self, wants_shutdown: bool):
        '''Send a shutdown/graceful command.'''

        message = json.dumps({
            'command': 'shutdown/graceful',
            'data': {
                'wants_shutdown': wants_shutdown
            }
        })

        self.message_queue.put_nowait(message)

    def send_shutdown_immediate(self):
        '''Send a shutdown/immediate command.'''

        message = json.dumps({
            'command': 'shutdown/immediate'
        })

        self.message_queue.put_nowait(message)

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
    
    def __init__(self, state: str, query: str, ephemeral_context: bool, action_names: list[str]):
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