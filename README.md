# Traider

## 🧠 Overview

Traider is an automated crypto trading bot for Binance, built around a dynamic, risk-managed hybrid strategy. It features a robust PnL tracking system, persistent trade logging, and a powerful analysis toolkit.

- **Dynamic Strategy Selection:** Switches between breakout and grid trading based on market volatility (ATR).
- **Active Position Monitoring:** A background service actively monitors placed orders to track the entire lifecycle of a trade.
- **Automated PnL Calculation:** Automatically calculates and logs the realized Profit & Loss for every completed trade.
- **Persistent Trade Logging:** Saves a detailed history of all live and testnet trades to `live_trades.csv` and `testnet_trades.csv`.
- **In-depth Analysis:** Comes with a script to analyze your trade logs and generate detailed performance reports.
- **Multi-Currency Support:** The provided Docker Compose setup allows for running separate, optimized bot instances for multiple trading pairs simultaneously.
- **Enhanced Backtesting:** Features realistic backtesting with dynamic slippage, latency simulation, and exchange constraints.
- **Parameter Optimization:** Automated parameter optimization using Optuna to find the most profitable strategy configurations.
- **Sentiment Analysis Integration:** Deep sentiment integration for more informed trading decisions based on market sentiment.
 - **Live Sentiment & Safety Gate:** Real-time sentiment from CryptoPanic, NewsAPI, RSS, plus Fear & Greed Index to gate trades.

---

## 📦 Features

- Binance API live and testnet trading support
- **Persistent CSV Trade Logging**
- **Automated PnL Calculation & Performance Analysis**
- **Active Order Monitoring & Position Management**
- Dynamic strategy selection using ATR
- Breakout and grid trading strategies
- **Advanced Sentiment Analysis** for risk management and position sizing
- **Realistic Backtesting Engine** with dynamic slippage, latency simulation, and exchange constraints
- **Parameter Optimization** with Optuna, including walk-forward validation
- **Historical Data Acquisition** for sentiment and price data
- **Bollinger Bands** integration for enhanced signal generation
- **Comprehensive Performance Metrics** for strategy evaluation

---

## ⚙️ Installation

1.  Clone the repo:
    ```bash
    git clone https://github.com/iyeque/Traider.git
    cd Traider
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Create your .env file:
    ```bash
    cp .env.example .env
    ```
4.  Add your API keys and configure your strategy in the `.env` file. Set `BINANCE_ENV` to `TESTNET` to use the testnet.

### Environment variables for live sentiment
- `CRYPTOPANIC_API_KEY` (optional, recommended)
- `NEWSAPI_KEY` (optional)
If not provided or sources return no data, the bot falls back to RSS feeds and a neutral score.

---

## 💻 Running the Bot

### With Docker (Recommended for Multi-Currency)
The `docker-compose.yml` is pre-configured to run four bot instances, one for each currency (BNB, BTC, ETH, SOL), with individually tuned parameters.
```bash
docker-compose up -d
```
View logs for a specific bot:
```bash
docker-compose logs -f traider-bot-btc
```

### Natively
When you run the bot natively, it starts the main trading logic and the background `OrderMonitor` to track trade executions and PnL.
```bash
python main.py
```
The bot evaluates market safety each cycle using live sentiment and the Fear & Greed Index (see below). Tune thresholds in `config`.

---

## 📊 Monitoring and Analysis

This project provides several tools to monitor your bot's activity and analyze its performance.

### 1. Trade Log Analysis (Recommended)

The most powerful analysis tool is the `analyze_trades.py` script. It reads your CSV trade logs and generates a comprehensive performance report with key metrics like Net Profit, Win Rate, and Profit Factor, along with a PnL distribution chart.

-   **Live Trades:** `live_trades.csv`
-   **Testnet Trades:** `testnet_trades.csv`

**How to run the analysis:**
```bash
# To analyze your live trades
py backtest/analyze_trades.py live_trades.csv

# To analyze your testnet trades
py backtest/analyze_trades.py testnet_trades.csv
```

### 2. Enhanced Backtesting

The backtesting engine (`backtest/backtest.py`) now provides more realistic simulations with:

- **Dynamic Slippage:** Slippage calculated based on trade quantity
- **Latency Simulation:** Realistic execution delays
- **Exchange Constraints:** MIN_NOTIONAL and LOT_SIZE checks
- **Global Drawdown Control:** Stops trading if maximum drawdown is hit
- **Trade Count Limit:** Limits the number of trades in a backtest
- **Sentiment Integration:** Uses historical sentiment data
- **Comprehensive Metrics:** Detailed performance metrics

### 3. Live Sentiment Integration

Live sentiment is fetched by `data_acquisition/fetch_live_sentiment.py` (CryptoPanic, NewsAPI, RSS) and the Fear & Greed Index. It is consumed by `bot/sentiment_engine.is_market_safe()` which updates `LiveTradingStats`. 

- Safety gate: `main.py` calls `is_market_safe(min_sentiment, min_fear_greed)` before running strategies.
- Signal context: `breakout_strategy` pulls the latest value via `LiveTradingStats().get_sentiment()`.
- Configuration: tune `SENTIMENT_THRESHOLD_POSITIVE`, `SENTIMENT_THRESHOLD_NEGATIVE`, and `FEAR_GREED_THRESHOLD` in `config`.

### 3. Real-time Dashboard

The dashboard provides a simple, real-time web interface to see high-level stats of a single running bot instance.

**How to run it:**
```bash
# Run this in a separate terminal
py manual_dashboard.py
```
Then open your browser to `http://127.0.0.1:8181`.

### 3. Raw Account Data Check

For a quick, on-demand check of your raw testnet account data (all balances and full trade history from the exchange), use the `check_testnet.py` script.
```bash
py check_testnet.py
```

---

## 🧪 Automated Testing

Unit tests are provided for core modules to ensure reliability and correctness:
- `bot/test_strategy.py`: Tests the signal generation logic in `strategy.py`.

Run all tests before deploying or running the bot to catch bugs early:
```bash
python -m unittest discover bot
```

---

## 📁 Project Structure

```bash
traider/
├── bot/
│   ├── strategy.py        # Signal generator & indicators
│   ├── trading.py         # Executes trades with SL/TP
│   ├── grid.py            # Grid ladder logic
│   ├── sentiment_engine.py# Live sentiment & market safety gate
│   ├── position_manager.py# Singleton to manage open positions
│   ├── order_monitor.py   # Background service to track fills and PnL
│   ├── trade_logger.py    # Handles writing trades to CSV
│   ├── news_utils.py      # News data processing
│   ├── rss_utils.py       # RSS feed processing
│   └── ...
├── backtest/
│   ├── backtest.py        # Enhanced backtesting engine
│   ├── optimize_params.py # Parameter optimization with Optuna
│   ├── analyze_trades.py  # Trade analysis script
│   ├── optimization_results/ # Stores optimization results
├── data_acquisition/      # Scripts for fetching market data
│   ├── fetch_historical_data.py # Fetches historical price/sentiment data
│   ├── fetch_live_sentiment.py  # Fetches live sentiment & Fear & Greed Index
├── .env.example           # Example environment variables
├── config.py              # Configuration management
├── live_trades.csv        # Auto-generated log for live trades
├── testnet_trades.csv     # Auto-generated log for testnet trades
├── check_testnet.py       # Utility to check testnet account
├── main.py                # Main bot runner
├── manual_dashboard.py    # Real-time monitoring dashboard
├── CHANGELOG.md           # Detailed change history
└── README.md
```

---

## 🔐 Security Notes

-   Never commit your `.env` file or API keys.
-   Always use IP whitelisting on the Binance API.
-   Start with small amounts for live testing or use the Binance testnet.

---

## 🛡️ Disclaimer

This is NOT financial advice. You are fully responsible for your own trades, wins, and losses. Use it at your own risk.