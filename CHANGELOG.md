# Changelog

## [Unreleased]

### Added
- Enhanced backtesting engine with realistic features:
  - Dynamic slippage calculation based on trade quantity
  - Latency simulation for realistic execution delays
  - Exchange constraints (MIN_NOTIONAL and LOT_SIZE checks)
  - Global drawdown control to stop trading if maximum drawdown is hit
  - Trade count limit to control the number of trades in a backtest
- Advanced sentiment analysis integration:
  - Deep sentiment integration for trading decisions
  - Sentiment-based position sizing
  - Historical sentiment data acquisition
- Parameter optimization with Optuna:
  - Automated parameter search for optimal strategy configurations
  - Walk-forward validation to prevent overfitting
  - Optimization results storage for later analysis
- Bollinger Bands integration for enhanced signal generation
- Comprehensive performance metrics for strategy evaluation
- Historical data acquisition capabilities:
  - Price data fetching and processing
  - Sentiment data from multiple sources (CryptoPanic, NewsAPI, RSS feeds)
- Live sentiment acquisition for live trading:
  - `data_acquisition/fetch_live_sentiment.py` aggregates CryptoPanic, NewsAPI, RSS, and Fear & Greed Index
  - Integrated into `bot/sentiment_engine.is_market_safe()` and consumed by `main.py`
- Embedded in-process dashboard:
  - Lightweight aiohttp server integrated into `main.py` (port 8181)
  - Streams `LiveTradingStats` via WebSocket for real-time monitoring
- Type safety improvements:
  - Added null safety checks throughout the codebase
  - Fixed type errors in main.py
  - Improved type hints for better code reliability
  - Resolved `TextBlob.sentiment.polarity` typing with a safe accessor

### Changed
- Unified live and backtest logic for consistent behavior
- Improved configuration management with fallback defaults
- Enhanced real-time dashboard with more metrics
- Refactored code for better modularity and maintainability
- Docker Compose improvements for multi-currency setup:
  - Bind mounts added for persistent logs: `./:/app`, `./logs:/app/logs`
  - Exposed dashboard port on BTC service: `8181:8181`
- Backtest/optimization tooling:
  - Script-friendly imports (no package requirement) in `backtest.py` and `optimize_params.py`
  - `analyze_trades.py` now supports both live log (`status,pnl`) and backtest (`type,profit_loss`) formats

### Fixed
- Type errors in main.py with proper null safety checks
- Configuration loading to handle None values gracefully
- Various bug fixes and performance improvements

## [1.0.0] - Initial Release

### Added
- Binance API live and testnet trading support
- Persistent CSV trade logging
- Automated PnL calculation & performance analysis
- Active order monitoring & position management
- Dynamic strategy selection using ATR
- Breakout and grid trading strategies
- Basic sentiment filter for risk management
- Simple backtesting engine
- Basic parameter optimization