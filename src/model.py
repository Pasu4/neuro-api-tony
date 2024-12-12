from typing import Any, Optional

class HumanModel:
    
    def __init__(self):
        self.actions: list[NeuroAction] = []

    def add_action(self, action: 'NeuroAction'):
        '''Add an action to the list.'''
        
        self.actions.append(action)

    def remove_action(self, action: 'NeuroAction'):
        '''Remove an action from the list.'''
        
        self.actions.remove(action)

    def remove_action_by_name(self, name: str):
        '''Remove an action from the list by name.'''
        
        self.actions = [action for action in self.actions if action.name != name]

class NeuroAction:
    
    def __init__(self, name: str, description: str, schema: Optional[dict[str, Any]]):
        self.name = name
        self.description = description
        self.schema = schema
