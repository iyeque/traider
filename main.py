import asyncio
from datetime import datetime
from dotenv import load_dotenv
import os
import pandas as pd
from binance import AsyncClient
import logging
import time
from typing import Dict, Any, Optional, List, Tuple, Union
from aiohttp import web
import json

# Load environment variables first
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import centralized configuration
from config import config

# --- Import Bot Components ---
from bot.grid import place_grid_orders
from bot.trading import place_market_order_with_sl_tp, calculate_trade_size
from bot.sentiment_engine import is_market_safe
from bot.strategy_scheduler import StrategyScheduler
from bot.position_manager import PositionManager # Now a singleton
from bot.strategy import get_data, generate_signal, calculate_atr, calculate_rsi, calculate_macd, calculate_bollinger_bands
from bot.order_monitor import OrderMonitor # Import the new monitor

# --- Access Configuration Values ---
BINANCE_API_KEY = config.get('BINANCE_API_KEY')
BINANCE_API_SECRET = config.get('BINANCE_API_SECRET')
SYMBOL = config.get('TRADE_SYMBOL')
INTERVAL = config.get('INTERVAL')
TRADE_INTERVAL_SECONDS = config.get_int('TRADE_INTERVAL_SECONDS')
BASE_RISK_PER_TRADE_PERCENT = config.get_float('RISK_PER_TRADE_PERCENT')
RISK_PER_TRADE_PERCENT = BASE_RISK_PER_TRADE_PERCENT
TRADE_MODE = config.get('TRADE_MODE')
FIXED_TRADE_AMOUNT_USDT = config.get_float('FIXED_TRADE_AMOUNT_USDT')
SENTIMENT_SIZING_MULTIPLIER = config.get_float('SENTIMENT_SIZING_MULTIPLIER')
ATR_PERIOD = config.get_int('ATR_PERIOD')
ATR_TREND_THRESHOLD = config.get_float('ATR_TREND_THRESHOLD')
BREAKOUT_RR_RATIO = config.get_float('BREAKOUT_RR_RATIO')
GRID_LEVELS = config.get_int('GRID_LEVELS')
GRID_STEP_PERCENT = config.get_float('GRID_STEP_PERCENT')
GRID_PROFIT_TARGET_PERCENT = config.get_float('GRID_PROFIT_TARGET_PERCENT')
GRID_INVALIDATION_PERCENT = config.get_float('GRID_INVALIDATION_PERCENT')
SENTIMENT_THRESHOLD_POSITIVE = config.get_float('SENTIMENT_THRESHOLD_POSITIVE')
SENTIMENT_THRESHOLD_NEGATIVE = config.get_float('SENTIMENT_THRESHOLD_NEGATIVE')
BASE_RSI_OVERSOLD = config.get_float('BASE_RSI_OVERSOLD')
BASE_RSI_OVERBOUGHT = config.get_float('BASE_RSI_OVERBOUGHT')
USE_BOLLINGER_BANDS = config.get_bool('USE_BOLLINGER_BANDS')
BB_WINDOW = config.get_int('BB_WINDOW')
BB_WINDOW_DEV = config.get_float('BB_WINDOW_DEV')
FEAR_GREED_THRESHOLD = config.get_int('FEAR_GREED_THRESHOLD')

class BotState:
    def __init__(self, client: AsyncClient):
        self.last_run_time: datetime | None = None
        self.active = True
        self.client = client

# --- Initialize Singletons ---
position_manager = PositionManager()
scheduler = StrategyScheduler()


class EmbeddedDashboard:
    def __init__(self, stats_provider):
        self._stats_provider = stats_provider
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self, port: int = 8181):
        self._app = web.Application()
        self._app.add_routes([
            web.get('/', self._handle_index),
            web.get('/ws', self._handle_ws),
        ])
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, '0.0.0.0', port)
        await self._site.start()
        logging.info(f"Dashboard started on http://0.0.0.0:{port}")

    async def stop(self):
        try:
            if self._site is not None:
                await self._site.stop()
            if self._runner is not None:
                await self._runner.cleanup()
        except Exception as e:
            logging.error(f"Error stopping dashboard: {e}")

    async def _handle_index(self, request: web.Request):
        return web.Response(text='''
        <html>
            <head>
                <title>Trading Dashboard</title>
                <style>
                    body { font-family: Arial, sans-serif; background: #181c20; color: #f3f3f3; margin: 0; padding: 0; }
                    .container { max-width: 800px; margin: 40px auto; background: #23272b; border-radius: 10px; box-shadow: 0 2px 8px #0008; padding: 32px; }
                    h1 { text-align: center; color: #4fd1c5; }
                    .stats { display: flex; justify-content: space-around; margin-bottom: 32px; flex-wrap: wrap; gap: 12px; }
                    .stat { background: #2d333b; border-radius: 8px; padding: 24px 32px; text-align: center; min-width: 120px; }
                    .stat-title { color: #a0aec0; font-size: 1.1em; }
                    .stat-value { font-size: 2em; font-weight: bold; color: #4fd1c5; }
                    .section { margin-top: 32px; }
                    table { width: 100%; border-collapse: collapse; background: #23272b; }
                    th, td { padding: 10px; border-bottom: 1px solid #333; text-align: left; }
                    th { color: #4fd1c5; }
                    tr:last-child td { border-bottom: none; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Trading Dashboard</h1>
                    <div class="stats">
                        <div class="stat"><div class="stat-title">Trades</div><div class="stat-value" id="trades">0</div></div>
                        <div class="stat"><div class="stat-title">Profit</div><div class="stat-value" id="profit">$0.00</div></div>
                        <div class="stat"><div class="stat-title">Win Rate</div><div class="stat-value" id="win_rate">0%</div></div>
                        <div class="stat"><div class="stat-title">Consec. Losses</div><div class="stat-value" id="consecutive_losses">0</div></div>
                        <div class="stat"><div class="stat-title">Active Strategies</div><div class="stat-value" id="active_strategies">0</div></div>
                        <div class="stat"><div class="stat-title">Sentiment</div><div class="stat-value" id="sentiment">-</div></div>
                        <div class="stat"><div class="stat-title">Galaxy Score</div><div class="stat-value" id="galaxy_score">-</div></div>
                    </div>
                    <div class="section">
                        <h2>Recent Trades</h2>
                        <table>
                            <thead>
                                <tr><th>Symbol</th><th>Side</th><th>Quantity</th><th>Profit</th><th>Timestamp</th></tr>
                            </thead>
                            <tbody id="trade_history"></tbody>
                        </table>
                    </div>
                </div>
                <script>
                    const ws = new WebSocket('ws://' + location.host + '/ws');
                    ws.onmessage = (event) => {
                        const data = JSON.parse(event.data);
                        document.getElementById('trades').textContent = data.trades;
                        document.getElementById('profit').textContent = '$' + Number(data.profit || 0).toFixed(2);
                        document.getElementById('win_rate').textContent = (Number(data.win_rate || 0) * 100).toFixed(2) + '%';
                        document.getElementById('consecutive_losses').textContent = data.consecutive_losses || 0;
                        document.getElementById('active_strategies').textContent = data.active_strategies || 0;
                        document.getElementById('sentiment').textContent = (data.last_sentiment !== null && data.last_sentiment !== undefined) ? Number(data.last_sentiment).toFixed(2) : '-';
                        document.getElementById('galaxy_score').textContent = (data.last_galaxy_score !== null && data.last_galaxy_score !== undefined) ? data.last_galaxy_score : '-';
                        const tbody = document.getElementById('trade_history');
                        tbody.innerHTML = '';
                        (data.trade_history || []).slice(-10).reverse().forEach(trade => {
                            const tr = document.createElement('tr');
                            const ts = trade.timestamp ? new Date(trade.timestamp).toLocaleString() : '-';
                            tr.innerHTML = `<td>${trade.symbol || '-'}</td><td>${trade.side || '-'}</td><td>${trade.quantity || '-'}</td><td>${(trade.profit || 0).toFixed ? trade.profit.toFixed(2) : trade.profit}</td><td>${ts}</td>`;
                            tbody.appendChild(tr);
                        });
                    };
                </script>
            </body>
        </html>
        ''', content_type='text/html')

    async def _handle_ws(self, request: web.Request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        try:
            while True:
                stats = self._stats_provider.get_stats()
                await ws.send_str(json.dumps(stats, default=str))
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Dashboard WS error: {e}")
        finally:
            await ws.close()
        return ws

async def get_account_balance(client: AsyncClient, quote_asset: str = 'USDT') -> float:
    try:
        balance = await client.get_asset_balance(asset=quote_asset)
        if balance:
            return float(balance['free'])
        return 0.0
    except Exception as e:
        logging.error(f"Error getting account balance for {quote_asset}: {e}")
        return 0.0

# --- Strategy Definitions ---
async def grid_strategy(bot_state):
    balance = await get_account_balance(bot_state.client)
    # Ensure RISK_PER_TRADE_PERCENT is not None before passing to calculate_trade_size
    risk_percent = RISK_PER_TRADE_PERCENT if RISK_PER_TRADE_PERCENT is not None else 1.0
    amount_to_risk = calculate_trade_size(balance, TRADE_MODE, risk_percent, 0) # Sentiment not used for grid sizing
    # Ensure all parameters are not None before passing to place_grid_orders
    grid_levels = GRID_LEVELS if GRID_LEVELS is not None else 3
    step_pct = GRID_STEP_PERCENT if GRID_STEP_PERCENT is not None else 1.0
    profit_target_pct = GRID_PROFIT_TARGET_PERCENT if GRID_PROFIT_TARGET_PERCENT is not None else 2.0
    invalidation_pct = GRID_INVALIDATION_PERCENT if GRID_INVALIDATION_PERCENT is not None else 5.0
    await place_grid_orders(
        bot_state.client,
        SYMBOL,
        base_qty=amount_to_risk,
        levels=grid_levels,
        step_pct=step_pct,
        profit_target_pct=profit_target_pct,
        invalidation_pct=invalidation_pct
    )
    return None

async def breakout_strategy(bot_state):
    df = await get_data(bot_state.client, SYMBOL, INTERVAL)
    if df is None or df.empty:
        logging.warning(f"Could not retrieve data for {SYMBOL}. Skipping breakout strategy.")
        return None

    df['RSI'] = calculate_rsi(df)
    df = calculate_macd(df)
    if USE_BOLLINGER_BANDS:
        # Ensure parameters are not None before passing to calculate_bollinger_bands
        bb_window = BB_WINDOW if BB_WINDOW is not None else 20
        bb_window_dev = BB_WINDOW_DEV if BB_WINDOW_DEV is not None else 2.0
        df = calculate_bollinger_bands(df, window=bb_window, window_dev=bb_window_dev)

    # Get live sentiment from the trading stats (which is updated by is_market_safe)
    from bot.trading_stats import LiveTradingStats
    sentiment_data = LiveTradingStats()
    sentiment = sentiment_data.get_sentiment()

    # --- Safely access DataFrame data ---
    rsi_val = df['RSI'].iloc[-1]
    macd_val = df['macd'].iloc[-1]
    macds_val = df['macd_signal'].iloc[-1]
    close_val = df['close'].iloc[-1]

    bb_bbl_val = None
    bb_bbh_val = None
    if USE_BOLLINGER_BANDS:
        bb_bbl_series = df.get('bb_bbl')
        if bb_bbl_series is not None and not bb_bbl_series.empty:
            bb_bbl_val = bb_bbl_series.iloc[-1]
        
        bb_bbh_series = df.get('bb_bbh')
        if bb_bbh_series is not None and not bb_bbh_series.empty:
            bb_bbh_val = bb_bbh_series.iloc[-1]

    # Ensure parameters are not None before passing to generate_signal
    sentiment_threshold_positive = SENTIMENT_THRESHOLD_POSITIVE if SENTIMENT_THRESHOLD_POSITIVE is not None else 0.1
    sentiment_threshold_negative = SENTIMENT_THRESHOLD_NEGATIVE if SENTIMENT_THRESHOLD_NEGATIVE is not None else -0.1
    base_rsi_oversold = BASE_RSI_OVERSOLD if BASE_RSI_OVERSOLD is not None else 30.0
    base_rsi_overbought = BASE_RSI_OVERBOUGHT if BASE_RSI_OVERBOUGHT is not None else 70.0
    use_bollinger_bands = USE_BOLLINGER_BANDS if USE_BOLLINGER_BANDS is not None else False
    
    signal = generate_signal(
        rsi=rsi_val, macd=macd_val, macd_signal=macds_val,
        sentiment=sentiment, sentiment_threshold_positive=sentiment_threshold_positive,
        sentiment_threshold_negative=sentiment_threshold_negative, base_rsi_oversold=base_rsi_oversold,
        base_rsi_overbought=base_rsi_overbought, use_bollinger_bands=use_bollinger_bands,
        bb_bbl=bb_bbl_val,
        bb_bbh=bb_bbh_val,
        current_close=close_val
    )
    if signal:
        balance = await get_account_balance(bot_state.client)
        # Ensure parameters are not None before passing to calculate_trade_size
        risk_percent = RISK_PER_TRADE_PERCENT if RISK_PER_TRADE_PERCENT is not None else 1.0
        fixed_amount = FIXED_TRADE_AMOUNT_USDT if FIXED_TRADE_AMOUNT_USDT is not None else 5.0
        sentiment_multiplier = SENTIMENT_SIZING_MULTIPLIER if SENTIMENT_SIZING_MULTIPLIER is not None else 0.0
        amount_to_risk = calculate_trade_size(balance, TRADE_MODE, risk_percent, sentiment, fixed_amount, sentiment_multiplier)
        # Ensure parameters are not None before passing to place_market_order_with_sl_tp
        rr_ratio = BREAKOUT_RR_RATIO if BREAKOUT_RR_RATIO is not None else 2.0
        atr_period = ATR_PERIOD if ATR_PERIOD is not None else 14
        await place_market_order_with_sl_tp(
            bot_state.client, SYMBOL, signal, amount_to_risk,
            rr_ratio=rr_ratio, atr_period=atr_period
        )
    return None

async def run_bot(bot_state):
    global RISK_PER_TRADE_PERCENT
    if not bot_state.active:
        logging.info("Bot is inactive.")
        return

    now = datetime.now()
    if bot_state.last_run_time and (now - bot_state.last_run_time).seconds < TRADE_INTERVAL_SECONDS:
        return

    logging.info(f"\nRunning bot at {now.strftime('%Y-%m-%d %H:%M:%S')}")

    # Ensure parameters are not None before passing to is_market_safe
    sentiment_threshold = SENTIMENT_THRESHOLD_POSITIVE if SENTIMENT_THRESHOLD_POSITIVE is not None else 0.1
    fear_greed_threshold = FEAR_GREED_THRESHOLD if FEAR_GREED_THRESHOLD is not None else 30
    if not is_market_safe(min_sentiment=sentiment_threshold, min_fear_greed=fear_greed_threshold):
        logging.warning("Market conditions not safe. Skipping trade.")
        return

    df = await get_data(bot_state.client, SYMBOL, INTERVAL)
    if df is None or df.empty:
        logging.warning(f"Could not retrieve data for {SYMBOL}. Skipping bot run.")
        return

    # Ensure ATR_PERIOD is not None before passing to calculate_atr
    atr_period = ATR_PERIOD if ATR_PERIOD is not None else 14
    atr = calculate_atr(df, period=atr_period).iloc[-1]
    price = df['close'].iloc[-1]

    market_context = {'market': 'trending' if atr / price > ATR_TREND_THRESHOLD else 'sideways'}
    logging.info(f"Market regime detected: {market_context['market']} (ATR: {atr:.2f})")

    selected = scheduler.select_strategy(market_context)
    if selected:
        await selected(bot_state)
    else:
        logging.info("No strategy selected for current market context.")

    bot_state.last_run_time = now

async def run_scheduler(bot_state):
    while True:
        await run_bot(bot_state)
        # Ensure TRADE_INTERVAL_SECONDS is not None before passing to asyncio.sleep
        interval = TRADE_INTERVAL_SECONDS if TRADE_INTERVAL_SECONDS is not None else 60
        await asyncio.sleep(interval)

async def main():
    client = None # Initialize client to None
    scheduler_task = None # Initialize to None
    monitor_task = None # Initialize to None
    dashboard = None
    try:
        client = await AsyncClient.create(BINANCE_API_KEY, BINANCE_API_SECRET)
        BINANCE_ENV = config.get('BINANCE_ENV', 'LIVE')
        if BINANCE_ENV == "TESTNET":
            testnet_url = config.get('BINANCE_TESTNET_BASE_URL')
            if not testnet_url:
                logging.warning("BINANCE_TESTNET_BASE_URL not set, using default testnet URL.")
                testnet_url = "https://testnet.binance.vision/api"
            client.API_URL = testnet_url

        bot_state = BotState(client)
        scheduler.add_strategy('grid', grid_strategy, lambda ctx: ctx.get('market') == 'sideways')
        scheduler.add_strategy('breakout', breakout_strategy, lambda ctx: ctx.get('market') == 'trending')

        order_monitor = OrderMonitor(client)
        monitor_task = asyncio.create_task(order_monitor.start())
        # Start embedded dashboard sharing LiveTradingStats instance
        from bot.trading_stats import LiveTradingStats
        dashboard = EmbeddedDashboard(LiveTradingStats())
        await dashboard.start(port=8181)
        scheduler_task = asyncio.create_task(run_scheduler(bot_state))

        await asyncio.gather(scheduler_task, monitor_task)

    except asyncio.CancelledError:
        logging.info("\nTasks cancelled due to shutdown.")
    except KeyboardInterrupt:
        logging.info("\nBot stopped by user. Initiating graceful shutdown...")
        # Cancel tasks only if they were created
        if scheduler_task:
            scheduler_task.cancel()
        if monitor_task:
            monitor_task.cancel()
        # Wait for tasks to complete their cancellation, only if they were created
        # Filter out None values before passing to asyncio.gather
        tasks_to_gather = [task for task in [scheduler_task, monitor_task] if task is not None]
        if tasks_to_gather: # Only gather if there are actual tasks
            await asyncio.gather(*tasks_to_gather, return_exceptions=True)
    except ConnectionError as e:
        logging.error(f"Connection error occurred: {e}", exc_info=True)
    except TimeoutError as e:
        logging.error(f"Timeout error occurred: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"An unexpected error occurred in main: {e}", exc_info=True)
    finally:
        if client:
            try:
                await client.close_connection() # Ensure client connection is closed
                logging.info("Binance client connection closed successfully.")
            except Exception as e:
                logging.error(f"Error closing Binance client connection: {e}")
        if dashboard:
            try:
                await dashboard.stop()
            except Exception as e:
                logging.error(f"Error stopping dashboard: {e}")

if __name__ == "__main__":
    asyncio.run(main())
