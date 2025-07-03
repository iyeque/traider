import asyncio
from datetime import datetime
from dotenv import load_dotenv
import os
import pandas as pd
from binance.client import Client
from bot.grid import place_grid_orders
from bot.trading import place_market_order_with_sl_tp
from bot.sentiment_engine import is_market_safe
from bot.strategy_scheduler import StrategyScheduler
from bot.position_manager import PositionManager
from bot.strategy import get_data, generate_signal, calculate_atr
import time

load_dotenv()

# Load environment variables
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
SYMBOL = os.getenv("TRADE_SYMBOL", "BTCUSDT")
INTERVAL = os.getenv("INTERVAL", "15m")
TRADE_INTERVAL_SECONDS = int(os.getenv("TRADE_INTERVAL_SECONDS", "300"))
RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "1.0"))
ATR_PERIOD = int(os.getenv("ATR_PERIOD", "14"))
ATR_TREND_THRESHOLD = float(os.getenv("ATR_TREND_THRESHOLD", "0.02"))
BREAKOUT_RR_RATIO = float(os.getenv("BREAKOUT_RR_RATIO", "2.5"))
GRID_LEVELS = int(os.getenv("GRID_LEVELS", "4"))
GRID_STEP_PERCENT = float(os.getenv("GRID_STEP_PERCENT", "1.0"))
GRID_PROFIT_TARGET_PERCENT = float(os.getenv("GRID_PROFIT_TARGET_PERCENT", "1.5"))

class BotState:
    def __init__(self, client):
        self.last_run_time: datetime | None = None
        self.total_trades = 0
        self.active = True
        self.client = client

position_manager = PositionManager()
scheduler = StrategyScheduler()

def get_account_balance(client: Client, quote_asset: str = 'USDT') -> float:
    try:
        balance = client.get_asset_balance(asset=quote_asset)
        return float(balance['free'])
    except Exception as e:
        print(f"Error getting account balance: {e}")
        return 0.0

def grid_strategy(bot_state):
    balance = get_account_balance(bot_state.client)
    amount_to_risk = balance * (RISK_PER_TRADE_PERCENT / 100)
    return place_grid_orders(
        bot_state.client,
        SYMBOL,
        base_qty=amount_to_risk,
        levels=GRID_LEVELS,
        step_pct=GRID_STEP_PERCENT,
        profit_target_pct=GRID_PROFIT_TARGET_PERCENT
    )

def breakout_strategy(bot_state):
    df = get_data(bot_state.client, SYMBOL, INTERVAL)
    signal = generate_signal(df, sentiment=1)  # Placeholder for real sentiment
    if signal:
        balance = get_account_balance(bot_state.client)
        amount_to_risk = balance * (RISK_PER_TRADE_PERCENT / 100)
        return place_market_order_with_sl_tp(
            bot_state.client,
            SYMBOL,
            signal,
            amount_to_risk,
            rr_ratio=BREAKOUT_RR_RATIO,
            atr_period=ATR_PERIOD
        )
    return None

async def run_bot(bot_state):
    if not bot_state.active:
        print("Bot is inactive.")
        return

    now = datetime.now()
    if bot_state.last_run_time and (now - bot_state.last_run_time).seconds < TRADE_INTERVAL_SECONDS:
        print("Waiting for next interval...")
        return

    print(f"\nRunning bot at {now.strftime('%Y-%m-%d %H:%M:%S')}")

    if not is_market_safe():
        print("Market conditions not safe. Skipping trade.")
        return

    df = get_data(bot_state.client, SYMBOL, INTERVAL)
    atr = calculate_atr(df, period=ATR_PERIOD).iloc[-1]
    price = df['close'].iloc[-1]
    market_context = {'market': 'trending' if atr / price > ATR_TREND_THRESHOLD else 'sideways'}
    print(f"Market regime detected: {market_context['market']} (ATR: {atr:.2f})")

    selected = scheduler.select_strategy(market_context)
    if selected:
        await selected(bot_state)

    bot_state.total_trades += 1
    bot_state.last_run_time = now
    print(f"Total trades executed: {bot_state.total_trades}")

async def run_scheduler(bot_state):
    while True:
        await run_bot(bot_state)
        await asyncio.sleep(TRADE_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
        server_time = client.get_server_time()
        time_offset = server_time['serverTime'] - int(time.time() * 1000)
        client.timestamp_offset = time_offset
        print(f"Time offset with Binance server is {time_offset}ms.")

        bot_state = BotState(client)
        scheduler.add_strategy('grid', grid_strategy, lambda ctx: ctx.get('market') == 'sideways')
        scheduler.add_strategy('breakout', breakout_strategy, lambda ctx: ctx.get('market') == 'trending')

        asyncio.run(run_scheduler(bot_state))
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
