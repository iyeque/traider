# crypto_trading_bot/main.py

from binance.client import Client
from dotenv import load_dotenv
import os
from bot.strategy import get_data, generate_signal
from bot.trading import place_market_order
from bot.grid import place_grid_orders
from bot.news_filter import is_market_safe

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

SYMBOL = "BTCUSDT"
INTERVAL = "1h"

def run_bot():
    print("🚀 Running Crypto Trading Bot")
    if not is_market_safe():
        print("🛑 Skipping trade due to negative news sentiment.")
        return

    df = get_data(SYMBOL, INTERVAL)
    signal = generate_signal(df)

    print(f"📈 Signal detected: {signal.upper()}")

    if signal == "grid_buy":
        place_grid_orders(client, SYMBOL, base_qty=50)
    elif signal == "breakout_buy":
        place_market_order(client, SYMBOL, "buy", quantity=0.001)
    elif signal == "sell":
        place_market_order(client, SYMBOL, "sell", quantity=0.001)
    else:
        print("⏸ No action taken (HOLD).")

if __name__ == "__main__":
    run_bot()
