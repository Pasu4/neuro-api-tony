from typing import Any, Optional

class TonyModel:
    
    def __init__(self):
        self.actions: list[NeuroAction] = []

    def add_action(self, action: 'NeuroAction'):
        '''Add an action to the list.'''
        
        self.actions.append(action)

    def remove_action(self, action: 'NeuroAction'):
        '''Remove an action from the list.'''
        
        self.actions.remove(action)
        pass

    def remove_action_by_name(self, name: str):
        '''Remove an action from the list by name.'''
        
        self.actions = [action for action in self.actions if action.name != name]
        pass

    def clear_actions(self):
        '''Clear all actions from the list.'''
        
        self.actions.clear()
        pass

    def has_action(self, name: str) -> bool:
        '''Check if an action exists in the list.'''
        
        return any(action.name == name for action in self.actions)
    
    def get_action_by_name(self, name: str) -> Optional['NeuroAction']:
        '''Get an action by name.'''
        
        for action in self.actions:
            if action.name == name:
                return action
        return None

class NeuroAction:
    
    def __init__(self, name: str, description: str, schema: Optional[dict[str, Any]]):
        self.name = name
        self.description = description
        self.schema = schema
