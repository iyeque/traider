# Traider

# 🧠 Crypto Trading Bot — Dynamic, Risk-Managed Hybrid Strategy

An automated crypto trading bot built for Binance that uses a **dynamic, risk-managed hybrid strategy**:

- 📈 **Dynamic Strategy Selection:** Automatically switches between breakout and grid trading based on market volatility (ATR).
- 💥 **Breakout Strategy:** Captures trends with market orders protected by OCO Stop-Loss and Take-Profit.
- 🧮 **Grid Strategy:** Accumulates positions in sideways markets with a ladder of limit orders.
- 🧠 **Sentiment Analysis:** Filters trades based on real-time news and social sentiment.
- 💰 **Dynamic Position Sizing:** Calculates order size based on a fixed percentage of your account balance.
- 🧪 **Backtesting Engine:** Includes a backtesting engine to evaluate strategy performance.

---

## 📦 Features

- ✅ Binance API live trading support
- ✅ Dynamic strategy selection using ATR
- ✅ Breakout strategy with OCO SL/TP
- ✅ Grid trading for sideways markets
- ✅ Dynamic position sizing based on risk
- ✅ News sentiment filter to avoid risky trades
- ✅ Backtesting engine with visual PnL plots

---

## ⚙️ Installation

1.  **Clone the repo**
    ```bash
    git clone https://github.com/iyeque/Traider.git
    cd Traider
    ```

2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Create your .env file**
    Copy from the example:
    ```bash
    cp .env.example .env
    ```

4.  **Add your API keys and configure your strategy in the `.env` file.**

---

## 💻 Running the Bot

### 🐳 Running with Docker (Recommended)

1.  **Build and run the Docker container:**
    ```bash
    docker-compose up -d
    ```

2.  **View the logs:**
    ```bash
    docker-compose logs -f
    ```

### 🐍 Running Natively

```bash
python main.py
```

---

## 📁 Project Structure

```bash
traider/
├── bot/
│   ├── strategy.py        # Signal generator & indicators (RSI, MACD, ATR)
│   ├── trading.py         # Executes trades with SL/TP
│   ├── grid.py            # Grid ladder logic
│   ├── sentiment_engine.py# Sentiment analysis
├── backtest/
│   ├── backtest.py        # Backtesting engine
├── .env.example           # Example environment variables
├── .env                   # Your environment variables (ignored by git)
├── Dockerfile
├── docker-compose.yml
├── main.py                # Main bot runner
├── requirements.txt
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
