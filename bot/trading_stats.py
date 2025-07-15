import threading
from typing import List, Dict, Any

class LiveTradingStats:
    def get_sentiment(self):
        """
        Returns the last sentiment score set by set_sentiment.
        """
        with self._lock:
            return self.last_sentiment
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
        self.winning_trades_count = 0
        self.trade_outcomes: List[bool] = [] # Initialize trade_outcomes
        self.last_sentiment = None
        self.last_galaxy_score = None
        self._lock = threading.Lock()

    def log_trade(self, trade: Dict[str, Any]):
        with self._lock:
            self.total_trades += 1
            profit = trade.get('profit', 0.0)
            self.profit += profit
            self.trade_history.append(trade)
            self.trade_outcomes.append(profit > 0) # Log True for win, False for loss
            if profit > 0:
                self.winning_trades_count += 1

    def set_active_strategies(self, count: int):
        with self._lock:
            self.active_strategies = count

    def set_sentiment(self, sentiment: float, galaxy_score: float):
        with self._lock:
            self.last_sentiment = sentiment
            self.last_galaxy_score = galaxy_score

    def get_consecutive_losses(self, window_size: int = 5) -> int:
        """
        Returns the number of consecutive losing trades within the last window_size trades.
        """
        with self._lock:
            if not self.trade_outcomes:
                return 0
            
            recent_outcomes = self.trade_outcomes[-window_size:]
            consecutive_losses = 0
            for outcome in reversed(recent_outcomes):
                if not outcome: # If it's a loss
                    consecutive_losses += 1
                else:
                    break # Stop counting if a win is encountered
            return consecutive_losses

    def get_stats(self):
        with self._lock:
            win_rate = self.winning_trades_count / self.total_trades if self.total_trades > 0 else 0
            consecutive_losses = self.get_consecutive_losses()
            return {
                'trades': self.total_trades,
                'profit': self.profit,
                'active_strategies': self.active_strategies,
                'trade_history': list(self.trade_history),
                'win_rate': win_rate,
                'consecutive_losses': consecutive_losses,
                'last_sentiment': self.last_sentiment,
                'last_galaxy_score': self.last_galaxy_score
            }