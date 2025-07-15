import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from ta.volatility import BollingerBands
import matplotlib.pyplot as plt
import os
from binance.client import Client
import time
import logging
from typing import Optional

# Import the sentiment data loader
from data_acquisition.fetch_sentiment import load_historical_sentiment
from bot.strategy import get_data, apply_indicators, generate_signal
from bot.trading import calculate_trade_size
from bot.exchange_info import get_symbol_info, format_quantity, get_min_notional

def load_data(csv_file):
    df = pd.read_csv(csv_file)
    # Use actual column names from the CSV
    # timestamp,open,high,low,close,volume
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    return df

def calculate_dynamic_slippage(quantity: float, price: float, base_slippage_pct: float = 0.0005, volume_factor: float = 0.000001) -> float:
    """
    Calculates dynamic slippage based on quantity and a base percentage.
    A higher quantity implies higher slippage.
    volume_factor is a placeholder for how much quantity impacts slippage.
    """
    # This is a simplified model. In reality, slippage depends on market depth and liquidity.
    # Here, we make it proportional to the quantity traded.
    slippage = base_slippage_pct + (quantity * volume_factor)
    return slippage

def strategy_backtest(client: Client,
                      df,
                      starting_balance: float = 10000,
                      fee_rate: float = 0.001,
                      base_slippage_pct: float = 0.0005, # Renamed from slippage_pct
                      volume_factor: float = 0.000001, # New parameter for dynamic slippage
                      latency_seconds: int = 0, # New parameter for latency simulation
                      max_drawdown_percent: float = 20.0, # New parameter for global stop-loss
                      max_trades: int = 0, # New parameter for trade count limit (0 means no limit)
                      sentiment_sizing_multiplier: float = 0.0, # New parameter for sentiment-based sizing
                      atr_period: int = 14,
                      atr_trend_threshold: float = 0.02,
                      breakout_rr_ratio: float = 2.5,
                      grid_levels: int = 4,
                      grid_step_percent: float = 1.0,
                      grid_profit_target_percent: float = 1.5,
                      grid_invalidation_percent: float = 2.0,
                      risk_per_trade_percent: float = 1.0,
                      trade_mode: str = 'PERCENTAGE',
                      fixed_trade_amount_usdt: float = 5.0,
                      sentiment_threshold_positive: float = 0.1,
                      sentiment_threshold_negative: float = -0.1,
                      base_rsi_oversold: float = 30,
                      base_rsi_overbought: float = 70,
                      use_bollinger_bands: bool = False, # New parameter for Bollinger Bands
                      bb_window: int = 20,
                      bb_window_dev: float = 2.0,
                      sentiment_csv_file: Optional[str] = None, # New parameter for historical sentiment
                      symbol: str = "BTCUSDT" # Pass symbol to get exchange info
                     ):
    balance = starting_balance
    peak_balance = starting_balance
    trade_log = []
    trade_count = 0
    
    # Metrics for analysis
    gross_profit = 0
    gross_loss = 0
    winning_trades = 0
    losing_trades = 0
    max_drawdown = 0
    current_drawdown = 0

    # current_position will track the state of the bot's open position
    # For grid, 'open_orders' could track individual limit orders
    current_position = {'quantity': 0, 'entry_price': 0, 'strategy': None, 'sl_price': None, 'tp_price': None, 'invalidation_price': None, 'open_orders': []}

    min_notional = get_min_notional(client, symbol)

    # Load historical sentiment data if provided
    sentiment_df = None
    if sentiment_csv_file and os.path.exists(sentiment_csv_file):
        sentiment_df = load_historical_sentiment(sentiment_csv_file)
        logging.info(f"Loaded historical sentiment data from {sentiment_csv_file}")
    else:
        logging.warning(f"Historical sentiment data not found at {sentiment_csv_file}. Sentiment will be neutral in backtest.")

    # Pre-calculate all necessary indicators
    df = apply_indicators(df, atr_period=atr_period, use_bollinger_bands=use_bollinger_bands, bb_window=bb_window, bb_window_dev=bb_window_dev)

    # Ensure we have enough data for indicators to be valid
    # Start loop after the longest indicator period (e.g., MACD's 26 or ATR's 14)
    start_index = max(atr_period, 26, bb_window if use_bollinger_bands else 0) # Adjust for BB window

    for i in range(start_index, len(df)):
        current_candle = df.iloc[i]
        price = current_candle['close']
        timestamp = current_candle['timestamp']
        atr = current_candle['ATR'] # Use pre-calculated ATR
        high_price = current_candle['high']
        low_price = current_candle['low']

        # Update peak balance
        peak_balance = max(peak_balance, balance)

        # Global Drawdown Check
        if balance < peak_balance * (1 - max_drawdown_percent / 100):
            logging.warning(f"🚨 GLOBAL DRAWDOWN HIT at {timestamp}: Balance {balance:.2f} dropped below {max_drawdown_percent}% of peak balance {peak_balance:.2f}. Stopping backtest.")
            # Simulate closing any open position before stopping
            if current_position['quantity'] > 0:
                # Calculate dynamic slippage for final exit
                slippage_amount = calculate_dynamic_slippage(current_position['quantity'], price, base_slippage_pct, volume_factor)
                exit_price = price * (1 - slippage_amount) # Apply slippage on final exit
                
                # Apply step size and min notional checks for final exit
                exit_quantity = format_quantity(client, symbol, current_position['quantity'])
                if float(exit_quantity) * exit_price < min_notional:
                    logging.warning(f"Skipping final exit sell due to min notional at {timestamp}. Qty: {exit_quantity}, Price: {exit_price}")
                    # If it can't meet min notional, assume position is stuck or closed at 0 for backtest simplicity
                    balance = 0 # Effectively lost all capital
                else:
                    trade_value = float(exit_quantity) * exit_price
                    fee = trade_value * fee_rate
                    balance_before_trade = balance
                    balance += (trade_value - fee)
                    logging.debug(f"DEBUG: Global Drawdown Exit - Balance before: {balance_before_trade:.2f}, Trade value: {trade_value:.2f}, Fee: {fee:.2f}, Balance after: {balance:.2f}")
                    trade_log.append({'type': 'global_drawdown_exit', 'price': exit_price, 'quantity': exit_quantity, 'balance': balance, 'timestamp': timestamp, 'profit_loss': (balance - starting_balance) if current_position['quantity'] == 0 else (balance - (current_position['quantity'] * current_position['entry_price']))})
            
            # Calculate final profit/loss for metrics
            final_profit_loss = balance - starting_balance
            # When global drawdown hits, it's a failure. Set metrics to reflect this.
            gross_profit = 0
            gross_loss = starting_balance # Represent total capital lost
            profit_factor = 0
            win_rate = 0
            avg_win = 0
            avg_loss = 0

            return pd.DataFrame(trade_log), 0, {
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown,
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss
            } # Stop backtest and return current results

        # Trade Count Limit Check
        if max_trades > 0 and trade_count >= max_trades:
            logging.info(f"📈 MAX TRADES ({max_trades}) REACHED at {timestamp}. Stopping backtest.")
            if current_position['quantity'] > 0:
                # Calculate dynamic slippage for final exit
                slippage_amount = calculate_dynamic_slippage(current_position['quantity'], price, base_slippage_pct, volume_factor)
                exit_price = price * (1 - slippage_amount) # Apply slippage on final exit
                
                # Apply step size and min notional checks for final exit
                exit_quantity = format_quantity(client, symbol, current_position['quantity'])
                if float(exit_quantity) * exit_price < min_notional:
                    logging.warning(f"Skipping final exit sell due to min notional at {timestamp}. Qty: {exit_quantity}, Price: {exit_price}")
                    balance = 0
                else:
                    trade_value = float(exit_quantity) * exit_price
                    fee = trade_value * fee_rate
                    balance_before_trade = balance
                    balance += (trade_value - fee)
                    logging.debug(f"DEBUG: Max Trades Exit - Balance before: {balance_before_trade:.2f}, Trade value: {trade_value:.2f}, Fee: {fee:.2f}, Balance after: {balance:.2f}")
                    trade_log.append({'type': 'max_trades_exit', 'price': exit_price, 'quantity': exit_quantity, 'balance': balance, 'timestamp': timestamp, 'profit_loss': (balance - starting_balance) if current_position['quantity'] == 0 else (balance - (current_position['quantity'] * current_position['entry_price']))})
            
            # Calculate final profit/loss for metrics
            final_profit_loss = balance - starting_balance
            if final_profit_loss > 0: gross_profit += final_profit_loss
            else: gross_loss += abs(final_profit_loss)

            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            win_rate = winning_trades / trade_count if trade_count > 0 else 0
            avg_win = gross_profit / winning_trades if winning_trades > 0 else 0
            avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0

            return pd.DataFrame(trade_log), balance, {
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown,
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss
            }

        # Determine execution candle based on latency
        execution_candle_index = i
        if latency_seconds > 0:
            # Find the next candle's open price for execution
            # This assumes latency pushes execution to the next full candle
            if i + 1 < len(df):
                execution_candle_index = i + 1
            else:
                # If it's the last candle, can't simulate latency to next candle
                continue # Skip this iteration if no next candle for latency
        
        execution_price = df.iloc[execution_candle_index]['open']
        execution_timestamp = df.iloc[execution_candle_index]['timestamp']

        # Update max_drawdown
        current_drawdown = (peak_balance - balance) / peak_balance * 100
        max_drawdown = max(max_drawdown, current_drawdown)

        # --- Get current sentiment ---
        current_sentiment = 0.0 # Default to neutral if no sentiment data
        if sentiment_df is not None:
            # Find the sentiment score for the current timestamp or the closest preceding one
            # This is a simplification; more robust alignment might be needed
            try:
                current_sentiment = sentiment_df.loc[timestamp]['sentiment_score']
            except KeyError:
                # If exact timestamp not found, try to find the nearest one
                # This requires sentiment_df to be sorted by index
                if not sentiment_df.empty:
                    # Find the closest sentiment data point before or at the current timestamp
                    closest_sentiment_idx = sentiment_df.index.asof(timestamp)
                    if pd.notna(closest_sentiment_idx):
                        current_sentiment = sentiment_df.loc[closest_sentiment_idx]['sentiment_score']
                    else:
                        current_sentiment = 0.0
                else:
                    current_sentiment = 0.0 # Default to neutral if no sentiment data

        # --- Grid Invalidation Check (from main.py) ---
        if current_position['strategy'] == 'grid' and current_position['quantity'] > 0:
            if current_position['invalidation_price'] and price < current_position['invalidation_price']:
                logging.info(f"🚨 GRID INVALIDATION at {timestamp}: Price {price:.2f} dropped below stop-loss {current_position['invalidation_price']:.2f}. Closing position.")
                # Simulate selling current holdings
                if current_position['quantity'] > 0:
                    # Calculate dynamic slippage for exit
                    slippage_amount = calculate_dynamic_slippage(current_position['quantity'], price, base_slippage_pct, volume_factor)
                    exit_price = price * (1 - slippage_amount) # Apply slippage on exit
                    
                    # Apply step size and min notional checks for exit
                    exit_quantity = format_quantity(client, symbol, current_position['quantity'])
                    if float(exit_quantity) * exit_price < min_notional:
                        logging.warning(f"Skipping grid invalidation sell due to min notional at {timestamp}. Qty: {exit_quantity}, Price: {exit_price}")
                        # In a real scenario, you might be stuck or forced to market sell at any price.
                        # For backtest, we'll just clear the position for simplicity if it can't meet min notional.
                        current_position = {'quantity': 0, 'entry_price': 0, 'strategy': None, 'sl_price': None, 'tp_price': None, 'invalidation_price': None, 'open_orders': []}
                        continue

                    trade_value = float(exit_quantity) * exit_price
                    fee = trade_value * fee_rate
                    balance += (trade_value - fee)
                    profit_loss = (exit_price - current_position['entry_price']) * current_position['quantity'] - fee
                    trade_log.append({'type': 'grid_invalidation_sell', 'price': exit_price, 'quantity': exit_quantity, 'balance': balance, 'timestamp': timestamp, 'profit_loss': profit_loss})
                    
                    # Update metrics
                    profit_loss = (exit_price - current_position['entry_price']) * current_position['quantity'] - fee
                    if profit_loss > 0: gross_profit += profit_loss; winning_trades += 1
                    else: gross_loss += abs(profit_loss); losing_trades += 1

                    current_position = {'quantity': 0, 'entry_price': 0, 'strategy': None, 'sl_price': None, 'tp_price': None, 'invalidation_price': None, 'open_orders': []}
                continue # Stop further actions in this cycle for this candle

        # --- Check for open position exit conditions (SL/TP for breakout) ---
        if current_position['strategy'] == 'breakout' and current_position['quantity'] > 0:
            if current_position['sl_price'] and price <= current_position['sl_price']:
                logging.info(f"📉 BREAKOUT STOP-LOSS HIT at {timestamp}: Price {price:.2f} hit SL {current_position['sl_price']:.2f}.")
                # Calculate dynamic slippage for exit
                slippage_amount = calculate_dynamic_slippage(current_position['quantity'], current_position['sl_price'], base_slippage_pct, volume_factor)
                exit_price = current_position['sl_price'] * (1 - slippage_amount) # Simulate exit at SL with slippage
                
                # Apply step size and min notional checks for exit
                exit_quantity = format_quantity(client, symbol, current_position['quantity'])
                if float(exit_quantity) * exit_price < min_notional:
                    logging.warning(f"Skipping breakout SL sell due to min notional at {timestamp}. Qty: {exit_quantity}, Price: {exit_price}")
                    current_position = {'quantity': 0, 'entry_price': 0, 'strategy': None, 'sl_price': None, 'tp_price': None, 'invalidation_price': None, 'open_orders': []}
                    continue

                trade_value = float(exit_quantity) * exit_price
                fee = trade_value * fee_rate
                balance += (trade_value - fee)
                profit_loss = (exit_price - current_position['entry_price']) * current_position['quantity'] - fee
                trade_log.append({'type': 'sell(breakout_sl)', 'price': exit_price, 'quantity': exit_quantity, 'balance': balance, 'timestamp': timestamp, 'profit_loss': profit_loss})
                
                # Update metrics
                profit_loss = (exit_price - current_position['entry_price']) * current_position['quantity'] - fee
                if profit_loss > 0: gross_profit += profit_loss; winning_trades += 1
                else: gross_loss += abs(profit_loss); losing_trades += 1

                current_position = {'quantity': 0, 'entry_price': 0, 'strategy': None, 'sl_price': None, 'tp_price': None, 'invalidation_price': None, 'open_orders': []}
                continue
            elif current_position['tp_price'] and price >= current_position['tp_price']:
                logging.info(f"📈 BREAKOUT TAKE-PROFIT HIT at {timestamp}: Price {price:.2f} hit TP {current_position['tp_price']:.2f}.")
                # Calculate dynamic slippage for exit
                slippage_amount = calculate_dynamic_slippage(current_position['quantity'], current_position['tp_price'], base_slippage_pct, volume_factor)
                exit_price = current_position['tp_price'] * (1 - slippage_amount) # Simulate exit at TP with slippage
                
                # Apply step size and min notional checks for exit
                exit_quantity = format_quantity(client, symbol, current_position['quantity'])
                if float(exit_quantity) * exit_price < min_notional:
                    logging.warning(f"Skipping breakout TP sell due to min notional at {timestamp}. Qty: {exit_quantity}, Price: {exit_price}")
                    current_position = {'quantity': 0, 'entry_price': 0, 'strategy': None, 'sl_price': None, 'tp_price': None, 'invalidation_price': None, 'open_orders': []}
                    continue

                trade_value = float(exit_quantity) * exit_price
                fee = trade_value * fee_rate
                balance += (trade_value - fee)
                profit_loss = (exit_price - current_position['entry_price']) * current_position['quantity'] - fee
                trade_log.append({'type': 'sell(breakout_tp)', 'price': exit_price, 'quantity': exit_quantity, 'balance': balance, 'timestamp': timestamp, 'profit_loss': profit_loss})
                
                # Update metrics
                profit_loss = (exit_price - current_position['entry_price']) * current_position['quantity'] - fee
                if profit_loss > 0: gross_profit += profit_loss; winning_trades += 1
                else: gross_loss += abs(profit_loss); losing_trades += 1

                current_position = {'quantity': 0, 'entry_price': 0, 'strategy': None, 'sl_price': None, 'tp_price': None, 'invalidation_price': None, 'open_orders': []}
                continue

        # --- Strategy Execution ---
        if current_position['quantity'] == 0: # Only enter a new trade if no open position
            amount_to_risk = calculate_trade_size(balance, trade_mode, risk_per_trade_percent, current_sentiment, fixed_trade_amount_usdt, sentiment_sizing_multiplier)

            market_context = 'trending' if atr / price > atr_trend_threshold else 'sideways'
            # logging.debug(f"Timestamp: {timestamp}, Price: {price:.2f}, ATR: {atr:.4f}, Market Context: {market_context}")

            if market_context == 'sideways':
                # --- Simulate Grid Strategy ---
                # Simplified simulation: we assume all grid levels are placed at once
                # and we check if price hits any of them within the current candle.
                # This is a simplification as real grid orders fill over time.
                
                # Calculate potential buy prices for grid levels
                grid_buy_prices = []
                for level in range(1, grid_levels + 1):
                    grid_buy_prices.append(price * (1 - (level * grid_step_percent / 100)))
                
                # Check if any grid level would have been hit by the low of the current candle
                filled_levels_count = 0
                for buy_p in grid_buy_prices:
                    if low_price <= buy_p:
                        filled_levels_count += 1
                
                if filled_levels_count > 0:
                    # Simulate buying into the grid
                    avg_entry_price = sum(grid_buy_prices[:filled_levels_count]) / filled_levels_count
                    amount_per_level_usdt = amount_to_risk / grid_levels
                    total_quantity_usdt = amount_per_level_usdt * filled_levels_count
                    total_quantity = total_quantity_usdt / avg_entry_price
                    logging.debug(f"DEBUG: amount_to_risk={amount_to_risk}, amount_per_level_usdt={amount_per_level_usdt}, total_quantity_usdt={total_quantity_usdt}, calculated_total_quantity={total_quantity}")
                    
                    # Apply step size and min notional checks for entry
                    if pd.isna(total_quantity) or total_quantity <= 0:
                        logging.warning(f"Skipping grid buy due to invalid total_quantity (NaN or <= 0) at {timestamp}. Calculated: {total_quantity}")
                        continue
                    total_quantity = format_quantity(client, symbol, total_quantity)
                    total_quantity = float(total_quantity)
                    if total_quantity * avg_entry_price < min_notional:
                        logging.warning(f"Skipping grid buy due to min notional at {timestamp}. Qty: {total_quantity}, Price: {avg_entry_price}")
                        continue

                    # Calculate dynamic slippage for entry
                    slippage_amount = calculate_dynamic_slippage(total_quantity, avg_entry_price, base_slippage_pct, volume_factor)
                    entry_price_with_slippage = avg_entry_price * (1 + slippage_amount)
                    fee = total_quantity * entry_price_with_slippage * fee_rate
                    balance_before_trade = balance
                    balance -= (total_quantity * entry_price_with_slippage + fee)
                    logging.debug(f"DEBUG: Grid Buy - Balance before: {balance_before_trade:.2f}, Trade cost: {(float(total_quantity) * entry_price_with_slippage + fee):.2f}, Balance after: {balance:.2f}")

                    # Calculate invalidation price for the grid
                    last_buy_price = price * (1 - (grid_levels * grid_step_percent / 100))
                    invalidation_price = last_buy_price * (1 - grid_invalidation_percent / 100)

                    current_position = {
                        'quantity': float(total_quantity),
                        'entry_price': entry_price_with_slippage,
                        'strategy': 'grid',
                        'invalidation_price': invalidation_price,
                        'timestamp': execution_timestamp, # Use execution timestamp
                        'filled_levels': filled_levels_count # Track how many levels filled
                    }
                    trade_log.append({'type': 'buy(grid)', 'price': entry_price_with_slippage, 'quantity': total_quantity, 'balance': balance, 'timestamp': execution_timestamp, 'profit_loss': 0.0})
                    logging.info(f"📊 GRID BUY at {execution_timestamp}: Price {entry_price_with_slippage:.2f}, Qty {total_quantity:.4f}, Levels Filled: {filled_levels_count}")
                    trade_count += 1 # Increment trade count on successful entry

            elif market_context == 'trending':
                # Simulate generate_signal from bot/strategy.py
                # For backtesting, we'll use a placeholder sentiment value for now.
                # In a real backtest, this would come from historical sentiment data.
                signal = generate_signal(rsi=current_candle['RSI'], 
                                         macd=current_candle['macd'], 
                                         macd_signal=current_candle['macd_signal'], 
                                         sentiment=current_sentiment, 
                                         sentiment_threshold_positive=sentiment_threshold_positive, 
                                         sentiment_threshold_negative=sentiment_threshold_negative, 
                                         base_rsi_oversold=base_rsi_oversold, 
                                         base_rsi_overbought=base_rsi_overbought, 
                                         use_bollinger_bands=use_bollinger_bands, 
                                         bb_bbl=current_candle.get('bb_bbl'), 
                                         bb_bbh=current_candle.get('bb_bbh'), 
                                         current_close=price)

                if signal == 'buy': # Only simulating buy signals for now
                    # Calculate dynamic slippage for entry
                    quantity_for_slippage_calc = amount_to_risk / execution_price # Estimate quantity for slippage calc
                    slippage_amount = calculate_dynamic_slippage(quantity_for_slippage_calc, execution_price, base_slippage_pct, volume_factor)
                    entry_price = execution_price * (1 + slippage_amount) # Simulate market order entry with slippage
                    
                    # Calculate SL/TP based on ATR and RR ratio
                    # Note: In live bot, ATR is calculated on 1m klines for SL/TP. Here, using current candle's ATR.
                    sl_price = entry_price - (2 * atr)
                    tp_price = entry_price + (breakout_rr_ratio * (entry_price - sl_price))

                    quantity = amount_to_risk / entry_price # Simple quantity calculation for backtest
                    
                    # Apply step size and min notional checks for entry
                    quantity = format_quantity(client, symbol, quantity)
                    if float(quantity) * entry_price < min_notional:
                        logging.warning(f"Skipping breakout buy due to min notional at {timestamp}. Qty: {quantity}, Price: {entry_price}")
                        continue

                    # Ensure quantity is positive and reasonable
                    if float(quantity) > 0 and balance >= (float(quantity) * entry_price):
                        fee = float(quantity) * entry_price * fee_rate
                        balance_before_trade = balance
                        balance -= (float(quantity) * entry_price + fee)
                        logging.debug(f"DEBUG: Breakout Buy - Balance before: {balance_before_trade:.2f}, Trade cost: {(float(quantity) * entry_price + fee):.2f}, Balance after: {balance:.2f}")
                        current_position = {
                            'quantity': float(quantity),
                            'entry_price': entry_price,
                            'strategy': 'breakout',
                            'sl_price': sl_price,
                            'tp_price': tp_price,
                            'timestamp': execution_timestamp # Use execution timestamp
                        }
                        trade_log.append({'type': 'buy(breakout)', 'price': entry_price, 'quantity': quantity, 'balance': balance, 'timestamp': execution_timestamp, 'profit_loss': 0.0})
                        logging.info(f"📈 BREAKOUT BUY at {execution_timestamp}: Price {entry_price:.2f}, Qty {quantity:.4f}, SL {sl_price:.2f}, TP {tp_price:.2f}")
                        trade_count += 1 # Increment trade count on successful entry
                    else:
                        logging.warning(f"Skipping breakout buy due to insufficient funds or invalid quantity at {timestamp}.")

        else: # If there's an open position, check for exit conditions (SL/TP for breakout, TP for grid levels)
            if current_position['strategy'] == 'grid' and current_position['quantity'] > 0:
                # Simulate grid take-profit
                # For simplicity, if price hits TP for any filled level, we assume that level exits.
                # This is a very simplified model and doesn't track individual TP orders.
                # A more robust simulation would track each filled grid order and its TP.
                
                # Calculate the TP price for the *average* entry of the filled levels
                # This is a simplification. Ideally, each filled level has its own TP.
                tp_price_for_grid = current_position['entry_price'] * (1 + grid_profit_target_percent / 100)

                if high_price >= tp_price_for_grid:
                    logging.info(f"✅ GRID TAKE-PROFIT HIT at {timestamp}: Price {high_price:.2f} hit TP {tp_price_for_grid:.2f}.")
                    # Calculate dynamic slippage for exit
                    slippage_amount = calculate_dynamic_slippage(current_position['quantity'], tp_price_for_grid, base_slippage_pct, volume_factor)
                    exit_price = tp_price_for_grid * (1 - slippage_amount) # Simulate exit at TP with slippage
                    
                    # Apply step size and min notional checks for exit
                    exit_quantity = format_quantity(client, symbol, current_position['quantity'])
                    if float(exit_quantity) * exit_price < min_notional:
                        logging.warning(f"Skipping grid TP sell due to min notional at {timestamp}. Qty: {exit_quantity}, Price: {exit_price}")
                        current_position = {'quantity': 0, 'entry_price': 0, 'strategy': None, 'sl_price': None, 'tp_price': None, 'invalidation_price': None, 'open_orders': []}
                        continue

                    trade_value = float(exit_quantity) * exit_price
                    fee = trade_value * fee_rate
                    balance += (trade_value - fee)
                    profit_loss = (exit_price - current_position['entry_price']) * current_position['quantity'] - fee
                    trade_log.append({'type': 'sell(grid_tp)', 'price': exit_price, 'quantity': exit_quantity, 'balance': balance, 'timestamp': timestamp, 'profit_loss': profit_loss})
                    
                    # Update metrics
                    profit_loss = (exit_price - current_position['entry_price']) * current_position['quantity'] - fee
                    if profit_loss > 0: gross_profit += profit_loss; winning_trades += 1
                    else: gross_loss += abs(profit_loss); losing_trades += 1

                    current_position = {'quantity': 0, 'entry_price': 0, 'strategy': None, 'sl_price': None, 'tp_price': None, 'invalidation_price': None, 'open_orders': []}

    # If still in a position at the end of the backtest, exit at the last known price
    logging.debug(f"DEBUG: End of backtest. current_position: {current_position}, df.iloc[-1]: {df.iloc[-1]}")
    if current_position['quantity'] > 0:
        # Calculate dynamic slippage for final exit
        slippage_amount = calculate_dynamic_slippage(current_position['quantity'], df['close'].iloc[-1], base_slippage_pct, volume_factor)
        final_price = df['close'].iloc[-1] * (1 - slippage_amount) # Apply slippage on final exit
        
        # Apply step size and min notional checks for final exit
        exit_quantity = format_quantity(client, symbol, current_position['quantity'])
        if float(exit_quantity) * final_price < min_notional:
            logging.warning(f"Skipping final exit sell due to min notional at {df['timestamp'].iloc[-1]}. Qty: {exit_quantity}, Price: {final_price}")
            # If it can't meet min notional, assume position is stuck or closed at 0 for backtest simplicity
            balance = 0 # Effectively lost all capital
        else:
            trade_value = float(exit_quantity) * final_price
            fee = trade_value * fee_rate
            balance_before_trade = balance
            balance += (trade_value - fee)
            logging.debug(f"DEBUG: Final Exit - Balance before: {balance_before_trade:.2f}, Trade value: {trade_value:.2f}, Fee: {fee:.2f}, Balance after: {balance:.2f}")
            trade_log.append({'type': 'final_exit', 'price': final_price, 'quantity': exit_quantity, 'balance': balance, 'timestamp': df['timestamp'].iloc[-1], 'profit_loss': (final_price - current_position['entry_price']) * current_position['quantity'] - fee if current_position['quantity'] > 0 else 0.0})

    # Final metrics calculation
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    win_rate = winning_trades / trade_count if trade_count > 0 else 0
    avg_win = gross_profit / winning_trades if winning_trades > 0 else 0
    avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0

    return pd.DataFrame(trade_log), balance, {
        'profit_factor': profit_factor,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss
    }

def plot_performance(trades, df):
    plt.figure(figsize=(14, 6))
    plt.plot(df['timestamp'], df['close'], label='Price', alpha=0.5)

    buy_trades = trades[trades['type'].str.contains('buy')]
    sell_trades = trades[trades['type'].str.contains('sell|exit|invalidation', regex=True)]

    plt.scatter(buy_trades['timestamp'], buy_trades['price'], color='green', marker='^', s=100, label='Buy')
    plt.scatter(sell_trades['timestamp'], sell_trades['price'], color='red', marker='v', s=100, label='Sell')

    plt.title("Backtest Performance with Fees & Slippage")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.grid(True)
    plt.legend()
    plt.show()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    symbol = "BTCUSDT"
    interval = Client.KLINE_INTERVAL_1HOUR
    csv_file = f"backtest/{symbol}_1h.csv"
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    client = Client(api_key, api_secret)
    if not os.path.exists(csv_file):
        logging.info("Fetching historical data...")
        df = get_data(client, symbol, interval, limit=1000) # Fetch more data for backtest
        df.to_csv(csv_file, index=False)
        logging.info(f"Saved historical data to {csv_file}")
        time.sleep(1) # Give a moment for file to be written
    df = load_data(csv_file)
    # Load historical sentiment data (assuming you have a CSV named 'historical_sentiment.csv')
    # You would need to create this file from your data acquisition process
    historical_sentiment_csv = "data_acquisition/historical_sentiment.csv"
    if os.path.exists(historical_sentiment_csv):
        sentiment_data_for_backtest = load_historical_sentiment(historical_sentiment_csv)
        logging.info(f"Loaded historical sentiment data from {historical_sentiment_csv}")
    else:
        logging.warning(f"Historical sentiment data not found at {historical_sentiment_csv}. Sentiment will be neutral in backtest.")
    # Example usage of strategy_backtest with default parameters
    trades, final_balance, metrics = strategy_backtest(
        client,
        df,
        starting_balance=10000,
        fee_rate=0.001,
        base_slippage_pct=0.0005,
        volume_factor=0.000001,
        latency_seconds=0,
        max_drawdown_percent=20.0,
        max_trades=0,
        sentiment_sizing_multiplier=0.0,
        atr_period=14,
        atr_trend_threshold=0.02,
        breakout_rr_ratio=2.5,
        grid_levels=4,
        grid_step_percent=1.0,
        grid_profit_target_percent=1.5,
        grid_invalidation_percent=2.0,
        risk_per_trade_percent=1.0,
        trade_mode='PERCENTAGE',
        fixed_trade_amount_usdt=5.0,
        sentiment_threshold_positive=0.1,
        sentiment_threshold_negative=-0.1,
        base_rsi_oversold=30,
        base_rsi_overbought=70,
        use_bollinger_bands=False,
        bb_window=20,
        bb_window_dev=2.0,
        sentiment_csv_file=historical_sentiment_csv # Pass the sentiment CSV file
    )
    logging.info(trades)
    logging.info(f"Final Balance (with fees & slippage): ${final_balance:.2f}")
    logging.info("--- Backtest Metrics ---")
    for key, value in metrics.items():
        logging.info(f"{key.replace('_', ' ').title()}: {value:.2f}")
    plot_performance(trades, df)
