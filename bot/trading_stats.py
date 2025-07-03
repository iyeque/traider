import threading
from typing import List, Dict, Any

class LiveTradingStats:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.reset()
            return cls._instance

    def reset(self):
        self.total_trades = 0
        self.profit = 0.0
        self.active_strategies = 0
        self.trade_history: List[Dict[str, Any]] = []
        self.last_sentiment = None
        self.last_galaxy_score = None
        self._lock = threading.Lock()

    def log_trade(self, trade: Dict[str, Any]):
        with self._lock:
            self.total_trades += 1
            profit = trade.get('profit', 0.0)
            self.profit += profit
            self.trade_history.append(trade)

    def set_active_strategies(self, count: int):
        with self._lock:
            self.active_strategies = count

    def set_sentiment(self, sentiment: float, galaxy_score: float):
        with self._lock:
            self.last_sentiment = sentiment
            self.last_galaxy_score = galaxy_score

    def get_stats(self):
        with self._lock:
            return {
                'trades': self.total_trades,
                'profit': self.profit,
                'active_strategies': self.active_strategies,
                'trade_history': list(self.trade_history),
                'last_sentiment': self.last_sentiment,
                'last_galaxy_score': self.last_galaxy_score
            } 