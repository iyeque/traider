import os
from typing import Dict, Any, Optional, Union, List
import logging

class Config:
    """Centralized configuration management for the Traider application.
    
    This class provides a single source of truth for all configuration parameters
    used throughout the application. It loads values from environment variables
    with appropriate type conversion and provides sensible defaults.
    
    Usage:
        from config import config
        
        # Access configuration values
        symbol = config.get('TRADE_SYMBOL')
        interval = config.get('INTERVAL')
        
        # Access with type conversion
        risk_percent = config.get_float('RISK_PER_TRADE_PERCENT')
        grid_levels = config.get_int('GRID_LEVELS')
        use_bollinger = config.get_bool('USE_BOLLINGER_BANDS')
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the configuration with default values."""
        self.values = {
            # Trading parameters
            'TRADE_SYMBOL': 'BTCUSDT',
            'INTERVAL': '15m',
            'TRADE_INTERVAL_SECONDS': 900,
            'RISK_PER_TRADE_PERCENT': 1.0,
            'TRADE_MODE': 'PERCENTAGE',  # PERCENTAGE or FIXED
            'FIXED_TRADE_AMOUNT_USDT': 10.0,
            'SENTIMENT_SIZING_MULTIPLIER': 1.0,
            
            # Technical indicators
            'ATR_PERIOD': 14,
            'ATR_TREND_THRESHOLD': 0.02,
            'BREAKOUT_RR_RATIO': 2.5,
            'BASE_RSI_OVERSOLD': 30,
            'BASE_RSI_OVERBOUGHT': 70,
            'USE_BOLLINGER_BANDS': False,
            'BB_WINDOW': 20,
            'BB_WINDOW_DEV': 2.0,
            
            # Grid strategy parameters
            'GRID_LEVELS': 3,
            'GRID_STEP_PERCENT': 1.0,
            'GRID_PROFIT_TARGET_PERCENT': 1.5,
            'GRID_INVALIDATION_PERCENT': 2.0,
            
            # Sentiment parameters
            'SENTIMENT_THRESHOLD_POSITIVE': 0.1,
            'SENTIMENT_THRESHOLD_NEGATIVE': -0.1,
            'FEAR_GREED_THRESHOLD': 50,
            'MIN_FEAR_GREED': 30,
            
            # API keys and environment
            'BINANCE_API_KEY': '',
            'BINANCE_API_SECRET': '',
            'BINANCE_ENV': 'LIVE',  # LIVE or TESTNET
            'BINANCE_TESTNET_BASE_URL': 'https://testnet.binance.vision/api',
            
            # Backtest parameters
            'BACKTEST_START_DATE': '2023-01-01',
            'BACKTEST_END_DATE': '2023-12-31',
            'BACKTEST_INITIAL_BALANCE': 1000.0,
            'BACKTEST_FEE_RATE': 0.001,
            'BACKTEST_BASE_SLIPPAGE_PCT': 0.0005,
            'BACKTEST_VOLUME_FACTOR': 0.000001,
            'BACKTEST_MAX_DRAWDOWN_PCT': 25.0,
            'BACKTEST_MAX_TRADES': 100,
            
            # Logging and monitoring
            'LOG_LEVEL': 'INFO',
        }
        
        # Override defaults with environment variables
        self._load_from_env()
        
        # Configure logging based on settings
        self._configure_logging()
    
    def _load_from_env(self):
        """Load configuration values from environment variables."""
        for key in self.values.keys():
            env_value = os.getenv(key)
            if env_value is not None:
                # Convert to appropriate type based on default value
                default_value = self.values[key]
                if isinstance(default_value, bool):
                    self.values[key] = env_value.lower() == 'true'
                elif isinstance(default_value, int):
                    self.values[key] = int(env_value)
                elif isinstance(default_value, float):
                    self.values[key] = float(env_value)
                else:
                    self.values[key] = env_value
    
    def _configure_logging(self):
        """Configure logging based on the LOG_LEVEL setting."""
        log_level = self.get('LOG_LEVEL', 'INFO')
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO
        
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.
        
        Args:
            key: The configuration key to retrieve
            default: Default value if key is not found
            
        Returns:
            The configuration value or default if not found
        """
        return self.values.get(key, default)
    
    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Get a configuration value as an integer."""
        value = self.get(key, default)
        if value is None:
            return None
        return int(value)
    
    def get_float(self, key: str, default: Optional[float] = None) -> Optional[float]:
        """Get a configuration value as a float."""
        value = self.get(key, default)
        if value is None:
            return None
        return float(value)
    
    def get_bool(self, key: str, default: Optional[bool] = None) -> Optional[bool]:
        """Get a configuration value as a boolean."""
        value = self.get(key, default)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == 'true'
        return bool(value)
    
    def get_list(self, key: str, default: Optional[List] = None) -> Optional[List]:
        """Get a configuration value as a list.
        
        Args:
            key: The configuration key to retrieve
            default: Default value if key is not found
            
        Returns:
            The configuration value as a list, or default if not found
        """
        value = self.get(key, default)
        if value is None:
            return default
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return value.split(',')
        return [value]
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.
        
        Args:
            key: The configuration key to set
            value: The value to set
        """
        self.values[key] = value

# Create a singleton instance
config = Config()