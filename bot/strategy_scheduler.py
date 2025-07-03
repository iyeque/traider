import time
from typing import Callable

class StrategyScheduler:
    def __init__(self):
        self.strategies = []  # List of (name, function, condition)
        self.active_strategy = None

    def add_strategy(self, name: str, func: Callable, condition: Callable = None):
        self.strategies.append({'name': name, 'func': func, 'condition': condition})

    def select_strategy(self, market_context: dict):
        for strat in self.strategies:
            if strat['condition'] is None or strat['condition'](market_context):
                self.active_strategy = strat
                return strat['func']
        return None

    def run_active(self, *args, **kwargs):
        if self.active_strategy:
            return self.active_strategy['func'](*args, **kwargs)
        return None
