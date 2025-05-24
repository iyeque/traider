# Traider

# 🧠 Crypto Trading Bot — RSI + Breakout + Grid + Sentiment AI

An automated crypto trading bot built for Binance that uses a **hybrid strategy**:

- 📈 RSI & breakout trend detection
- 🧮 Grid laddering for sideways markets
- 🧠 Real-time crypto news sentiment analysis (CryptoPanic API)
- 🧪 Full backtesting engine
- 📊 Interactive live dashboard (Streamlit)

---

## 📦 Features

- ✅ Binance API live trading support
- ✅ RSI + Bollinger Band + ATR-based signals
- ✅ Grid buy logic (DCA-style range accumulation)
- ✅ News sentiment filter to avoid risky trades
- ✅ Backtesting engine with visual PnL plots
- ✅ Streamlit dashboard for real-time data and indicators

---

## ⚙️ Installation

1. **Clone the repo**  
   ```bash
   git clone https://github.com/iyeque/Traider.git
   cd Traider

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt


3. **Create your .env file**
   Copy from example:
   ```bash
   cp .env.example .env

4. **Add your API keys to .env**
   ```ini
   BINANCE_API_KEY=your_key
   BINANCE_API_SECRET=your_secret
   CRYPTOPANIC_API_KEY=your_token

---

## 💻 Running the Bot

🔁 Run the Trading Bot
This will:

-Check news sentiment
-Generate trading signals
-Place trades if signal is valid

bash
python main.py

📊 Launch the Dashboard
See real-time charts + RSI:

bash
streamlit run dashboard/dashboard.py

🧪 Run a Backtest
Backtest the strategy using historical data:

bash
python backtest/backtest.py

📝 Make sure you have a CSV file like BTCUSDT_1h.csv in the backtest/ folder with this format:

csv
timestamp,open,high,low,close,volume

## 📁 Project Structure
bash
traider/
├── bot/
│   ├── strategy.py        # Signal generator
│   ├── trading.py         # Executes trades
│   ├── grid.py            # Grid ladder logic
│   ├── news_filter.py     # Sentiment analysis
├── backtest/
│   ├── backtest.py        # Backtesting engine
│   └── BTCUSDT_1h.csv     # Historical data (example)
├── dashboard/
│   └── dashboard.py       # Streamlit dashboard
├── .env.example
├── main.py                # Main bot runner
├── requirements.txt
└── README.md

## 🔐 Security Notes
Never commit your .env file or keys.

Always use IP whitelisting on Binance API.

Use small amounts for live testing.

Run on Binance testnet before going live.

# #🧠 Future Features (Optional)
Telegram alerts

VPS/24-7 deployment

Docker support

Hyperparameter optimization (grid search)

## 🛡️ Disclaimer
This is NOT financial advice. You are fully responsible for your own trades, wins, and losses. Use it at your own risk.

## 🧑‍💻 Aknowledgements 
Made with 💼 by The Wolf of Wall Street GPT
Powered by OpenAI + Binance API + Python