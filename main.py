import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
import os
from binance.client import Client
from bot.grid import place_grid_orders
from bot.trading import place_market_order
from bot.sentiment_engine import is_market_safe  # updated for real-time sentiment

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
SYMBOL = os.getenv("TRADE_SYMBOL", "BTCUSDT")
INTERVAL = os.getenv("INTERVAL", "15m")
TRADE_INTERVAL_SECONDS = int(os.getenv("TRADE_INTERVAL_SECONDS", "300"))  # 5 min

class BotState:
    def __init__(self):
        self.last_run_time: datetime | None = None  # fixed type hint
        self.total_trades = 0
        self.active = True
        self.client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

bot_state = BotState()

async def run_bot():
    if not bot_state.active:
        print("❌ Bot is inactive.")
        return

    now = datetime.now()
    if bot_state.last_run_time and (now - bot_state.last_run_time).seconds < TRADE_INTERVAL_SECONDS:
        print("⏳ Waiting for next interval...")
        return

    print(f"\n📈 Running bot at {now.strftime('%Y-%m-%d %H:%M:%S')}")

    if not is_market_safe():
        print("🛑 Market conditions not safe. Skipping trade.")
        return

    # 🧠 Strategy: either grid or market buy — adjust as needed
    await place_grid_orders(bot_state.client, SYMBOL, base_qty=5)
    # await place_market_order(bot_state.client, SYMBOL, quantity=5)

    bot_state.total_trades += 1
    bot_state.last_run_time = now
    print(f"✅ Total trades executed: {bot_state.total_trades}")

async def run_scheduler():
    while True:
        await run_bot()
        await asyncio.sleep(TRADE_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        asyncio.run(run_scheduler())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
