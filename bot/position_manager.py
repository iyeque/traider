import threading
from typing import Dict, Any, Optional

class PositionManager:
    def __init__(self):
        self.positions = {}  # key: symbol, value: dict with entry, qty, side, etc.
        self.lock = threading.Lock()

    def open_position(self, symbol: str, entry_price: float, quantity: float, side: str, strategy: str):
        with self.lock:
            self.positions[symbol] = {
                'entry_price': entry_price,
                'quantity': quantity,
                'side': side,
                'strategy': strategy,
                'open': True,
                'unrealized_pnl': 0.0
            }

    def close_position(self, symbol: str, exit_price: float):
        with self.lock:
            pos = self.positions.get(symbol)
            if pos and pos['open']:
                pos['open'] = False
                pos['exit_price'] = exit_price
                pos['realized_pnl'] = (exit_price - pos['entry_price']) * pos['quantity'] * (1 if pos['side'] == 'buy' else -1)
                return pos['realized_pnl']
            return None

    def update_unrealized_pnl(self, symbol: str, current_price: float):
        with self.lock:
            pos = self.positions.get(symbol)
            if pos and pos['open']:
                pos['unrealized_pnl'] = (current_price - pos['entry_price']) * pos['quantity'] * (1 if pos['side'] == 'buy' else -1)

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self.positions.get(symbol)

    def get_all_positions(self):
        with self.lock:
            return dict(self.positions)
