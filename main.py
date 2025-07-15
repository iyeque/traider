import asyncio
from datetime import datetime
from dotenv import load_dotenv
import os
import pandas as pd
from binance.client import Client
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from bot.grid import place_grid_orders
from bot.trading_stats import LiveTradingStats # Import LiveTradingStats
from bot.trading import place_market_order_with_sl_tp, calculate_trade_size
from bot.sentiment_engine import is_market_safe
from bot.strategy_scheduler import StrategyScheduler
from bot.position_manager import PositionManager
from bot.strategy import get_data, generate_signal, calculate_atr, calculate_rsi, calculate_macd, calculate_bollinger_bands
import time

load_dotenv()

# Load environment variables
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
SYMBOL = os.getenv("TRADE_SYMBOL", "BTCUSDT")
INTERVAL = os.getenv("INTERVAL", "15m")
TRADE_INTERVAL_SECONDS = int(os.getenv("TRADE_INTERVAL_SECONDS", "300"))
BASE_RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "1.0")) # Store base risk
RISK_PER_TRADE_PERCENT = BASE_RISK_PER_TRADE_PERCENT # Current risk, can be adjusted
TRADE_MODE = os.getenv("TRADE_MODE", "PERCENTAGE")
FIXED_TRADE_AMOUNT_USDT = float(os.getenv("FIXED_TRADE_AMOUNT_USDT", "5.0"))
SENTIMENT_SIZING_MULTIPLIER = float(os.getenv("SENTIMENT_SIZING_MULTIPLIER", "0.0"))
ATR_PERIOD = int(os.getenv("ATR_PERIOD", "14"))
ATR_TREND_THRESHOLD = float(os.getenv("ATR_TREND_THRESHOLD", "0.02"))
BREAKOUT_RR_RATIO = float(os.getenv("BREAKOUT_RR_RATIO", "2.5"))
GRID_LEVELS = int(os.getenv("GRID_LEVELS", "4"))
GRID_STEP_PERCENT = float(os.getenv("GRID_STEP_PERCENT", "1.0"))
GRID_PROFIT_TARGET_PERCENT = float(os.getenv("GRID_PROFIT_TARGET_PERCENT", "1.5"))
GRID_INVALIDATION_PERCENT = float(os.getenv("GRID_INVALIDATION_PERCENT", "2.0"))
SENTIMENT_THRESHOLD_POSITIVE = float(os.getenv("SENTIMENT_THRESHOLD_POSITIVE", "0.1"))
SENTIMENT_THRESHOLD_NEGATIVE = float(os.getenv("SENTIMENT_THRESHOLD_NEGATIVE", "-0.1"))
BASE_RSI_OVERSOLD = float(os.getenv("BASE_RSI_OVERSOLD", "30"))
BASE_RSI_OVERBOUGHT = float(os.getenv("BASE_RSI_OVERBOUGHT", "70"))
USE_BOLLINGER_BANDS = os.getenv("USE_BOLLINGER_BANDS", "False").lower() == "true"
BB_WINDOW = int(os.getenv("BB_WINDOW", "20"))
BB_WINDOW_DEV = float(os.getenv("BB_WINDOW_DEV", "2.0"))

class BotState:
    def __init__(self, client):
        self.last_run_time: datetime | None = None
        self.total_trades = 0
        self.active = True
        self.client = client

position_manager = PositionManager()
scheduler = StrategyScheduler()
trading_stats = LiveTradingStats() # Get the singleton instance

def get_account_balance(client: Client, quote_asset: str = 'USDT') -> float:
    try:
        balance = client.get_asset_balance(asset=quote_asset)
        return float(balance['free'])
    except Exception as e:
        logging.error(f"Error getting account balance: {e}")
        return 0.0



def grid_strategy(bot_state):
    balance = get_account_balance(bot_state.client)
    is_market_safe() # This call updates the internal sentiment in LiveTradingStats
    sentiment = trading_stats.get_sentiment() # Retrieve the sentiment that was just updated
    amount_to_risk = calculate_trade_size(balance, TRADE_MODE, RISK_PER_TRADE_PERCENT, sentiment, FIXED_TRADE_AMOUNT_USDT, SENTIMENT_SIZING_MULTIPLIER)
    return place_grid_orders(
        bot_state.client,
        SYMBOL,
        base_qty=amount_to_risk,
        levels=GRID_LEVELS,
        step_pct=GRID_STEP_PERCENT,
        profit_target_pct=GRID_PROFIT_TARGET_PERCENT,
        invalidation_pct=GRID_INVALIDATION_PERCENT
    )

def breakout_strategy(bot_state):
    df = get_data(bot_state.client, SYMBOL, INTERVAL)
    
    # Calculate indicators
    df['RSI'] = calculate_rsi(df)
    df = calculate_macd(df)
    if USE_BOLLINGER_BANDS:
        df = calculate_bollinger_bands(df, window=BB_WINDOW, window_dev=BB_WINDOW_DEV)

    # Get live sentiment from sentiment_engine
    # Note: is_market_safe() updates LiveTradingStats with sentiment and fear_greed_index
    # We need to call it to get the latest sentiment, even if we don't use its boolean return directly here for signal generation
    is_market_safe() # This call updates the internal sentiment in LiveTradingStats
    sentiment = trading_stats.get_sentiment() # Retrieve the sentiment that was just updated

    signal = generate_signal(
        rsi=df['RSI'].iloc[-1],
        macd=df['macd'].iloc[-1],
        macd_signal=df['macd_signal'].iloc[-1],
        sentiment=sentiment,
        sentiment_threshold_positive=SENTIMENT_THRESHOLD_POSITIVE,
        sentiment_threshold_negative=SENTIMENT_THRESHOLD_NEGATIVE,
        base_rsi_oversold=BASE_RSI_OVERSOLD,
        base_rsi_overbought=BASE_RSI_OVERBOUGHT,
        use_bollinger_bands=USE_BOLLINGER_BANDS,
        bb_bbl=df.get('bb_bbl').iloc[-1] if USE_BOLLINGER_BANDS else None,
        bb_bbh=df.get('bb_bbh').iloc[-1] if USE_BOLLINGER_BANDS else None,
        current_close=df['close'].iloc[-1]
    )
    if signal:
        balance = get_account_balance(bot_state.client)
        amount_to_risk = calculate_trade_size(balance, TRADE_MODE, RISK_PER_TRADE_PERCENT, sentiment, FIXED_TRADE_AMOUNT_USDT, SENTIMENT_SIZING_MULTIPLIER) # Pass current risk and sentiment
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
    global RISK_PER_TRADE_PERCENT # Declare global to modify

    if not bot_state.active:
        logging.info("Bot is inactive.")
        return

    now = datetime.now()
    if bot_state.last_run_time and (now - bot_state.last_run_time).seconds < TRADE_INTERVAL_SECONDS:
        logging.info("Waiting for next interval...")
        return

    logging.info(f"\nRunning bot at {now.strftime('%Y-%m-%d %H:%M:%S')}")

    if not is_market_safe():
        logging.warning("Market conditions not safe. Skipping trade.")
        return

    # --- Adaptive Risk Management Logic ---
    consecutive_losses = trading_stats.get_consecutive_losses(window_size=5) # Check last 5 trades
    if consecutive_losses >= 3: # If 3 or more consecutive losses
        new_risk = max(BASE_RISK_PER_TRADE_PERCENT * 0.5, 0.1) # Reduce risk by 50%, but not below 0.1%
        if RISK_PER_TRADE_PERCENT > new_risk:
            RISK_PER_TRADE_PERCENT = new_risk
            logging.warning(f"📉 Consecutive losses ({consecutive_losses}). Reducing RISK_PER_TRADE_PERCENT to {RISK_PER_TRADE_PERCENT:.2f}%")
    elif consecutive_losses == 0 and RISK_PER_TRADE_PERCENT < BASE_RISK_PER_TRADE_PERCENT:
        # Gradually increase risk back if no recent losses and below base
        RISK_PER_TRADE_PERCENT = min(RISK_PER_TRADE_PERCENT + 0.1, BASE_RISK_PER_TRADE_PERCENT)
        logging.info(f"📈 No recent losses. Increasing RISK_PER_TRADE_PERCENT to {RISK_PER_TRADE_PERCENT:.2f}%")
    # --- End Adaptive Risk Management Logic ---

    df = get_data(bot_state.client, SYMBOL, INTERVAL)
    atr = calculate_atr(df, period=ATR_PERIOD).iloc[-1]
    price = df['close'].iloc[-1]

    # Check for grid invalidation
    active_position = position_manager.get_position(SYMBOL)
    if active_position and active_position.get('strategy') == 'grid' and active_position.get('open'):
        invalidation_price = active_position.get('invalidation_price')
        if invalidation_price and price < invalidation_price:
            logging.warning(f"🚨 GRID INVALIDATION: Price {{price}} dropped below stop-loss {{invalidation_price}}. Closing position.")
            # Implement logic to close all parts of the grid position here
            # This would involve cancelling open limit buy orders and market selling the current holdings
            position_manager.close_position(SYMBOL, price) # Mark as closed
            # For adaptive risk management, we need to log this as a loss
            trading_stats.log_trade({'profit': -1.0}) # Log a nominal loss for invalidation
            return # Stop further actions in this cycle

    market_context = {'market': 'trending' if atr / price > ATR_TREND_THRESHOLD else 'sideways'}
    logging.info(f"Market regime detected: {market_context['market']} (ATR: {atr:.2f})")

    selected = scheduler.select_strategy(market_context)
    if selected:
        await selected(bot_state)

    bot_state.total_trades += 1
    bot_state.last_run_time = now
    logging.info(f"Total trades executed: {bot_state.total_trades}")

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
        logging.info(f"Time offset with Binance server is {time_offset}ms.")

        bot_state = BotState(client)
        scheduler.add_strategy('grid', grid_strategy, lambda ctx: ctx.get('market') == 'sideways')
        scheduler.add_strategy('breakout', breakout_strategy, lambda ctx: ctx.get('market') == 'trending')

        asyncio.run(run_scheduler(bot_state))
    except KeyboardInterrupt:
        logging.info("\nBot stopped by user.")
