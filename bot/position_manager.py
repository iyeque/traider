import threading
from typing import Dict, Any, Optional, List

class PositionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the PositionManager singleton instance."""
        # The __init__ is called every time PositionManager() is invoked,
        # but the attributes are only set once.
        if not hasattr(self, 'initialized'):
            self.positions: Dict[str, List[Dict[str, Any]]] = {}
            self.initialized = True

    def open_position(self, symbol: str, order_id: str, entry_price: float, quantity: float, side: str, strategy: str, exit_order_ids: Optional[List[str]] = None, invalidation_price: Optional[float] = None):
        """Opens a new, specific position identified by its entry order ID."""
        with self._lock:
            if symbol not in self.positions:
                self.positions[symbol] = []
            
            if any(p['order_id'] == order_id for p in self.positions[symbol]):
                return

            self.positions[symbol].append({
                'order_id': order_id,
                'entry_price': entry_price,
                'quantity': quantity,
                'side': side,
                'strategy': strategy,
                'open': True,
                'exit_order_ids': exit_order_ids or [],
                'invalidation_price': invalidation_price
            })

    def close_position(self, symbol: str, order_id: str, exit_price: float) -> Optional[float]:
        """Closes a specific position and returns the realized PnL."""
        with self._lock:
            if symbol in self.positions:
                for pos in self.positions[symbol]:
                    if pos['order_id'] == order_id and pos['open']:
                        pos['open'] = False
                        pos['exit_price'] = exit_price
                        
                        pnl = (exit_price - pos['entry_price']) * pos['quantity']
                        if pos['side'] == 'sell':
                            pnl *= -1
                        
                        pos['realized_pnl'] = pnl
                        return pnl
            return None

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns a list of all open positions, optionally filtered by symbol."""
        with self._lock:
            open_positions = []
            symbols_to_check = [symbol] if symbol else self.positions.keys()
            for s in symbols_to_check:
                if s in self.positions:
                    for pos in self.positions[s]:
                        if pos.get('open', False):
                            pos_with_symbol = pos.copy()
                            pos_with_symbol['symbol'] = s
                            open_positions.append(pos_with_symbol)
            return open_positions

    def find_position_by_exit_order_id(self, exit_order_id: str) -> Optional[Dict[str, Any]]:
        """Finds an open position by one of its exit order IDs."""
        with self._lock:
            for symbol, positions in self.positions.items():
                for pos in positions:
                    if pos.get('open', False) and exit_order_id in pos.get('exit_order_ids', []):
                        pos_with_symbol = pos.copy()
                        pos_with_symbol['symbol'] = symbol
                        return pos_with_symbol
            return None