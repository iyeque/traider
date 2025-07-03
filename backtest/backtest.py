import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
import matplotlib.pyplot as plt
import os
from binance.client import Client
import time

def fetch_binance_klines(symbol, interval, start_str, end_str=None, filename=None, api_key=None, api_secret=None):
    """
    Fetch historical klines from Binance and save as CSV in backtest/ directory.
    """
    client = Client(api_key, api_secret)
    klines = client.get_historical_klines(symbol, interval, start_str, end_str)
    columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
               'quote_asset_volume', 'num_trades', 'taker_buy_base', 'taker_buy_quote', 'ignore']
    df = pd.DataFrame(klines, columns=columns)
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    if filename is None:
        filename = f"backtest/{symbol}_{interval}.csv"
    os.makedirs('backtest', exist_ok=True)
    df.to_csv(filename, index=False)
    print(f"Saved historical data to {filename}")
    return filename

def load_data(csv_file):
    df = pd.read_csv(csv_file)
    df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    return df

def apply_indicators(df):
    df['RSI'] = RSIIndicator(df['close'], window=14).rsi()
    df['ATR'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
    df['BB_Width'] = (df['high'].rolling(20).max() - df['low'].rolling(20).min()) / df['close']
    return df

def strategy_backtest(df, starting_balance=10000, position_size=0.05, fee_rate=0.001, slippage_pct=0.0005):
    balance = starting_balance
    position = 0
    entry_price = 0
    trade_log = []

    for i in range(20, len(df)):
        price = df['close'].iloc[i]
        rsi = df['RSI'].iloc[i]
        prev_high = df['high'].rolling(20).max().iloc[i - 1]
        bb_width = df['BB_Width'].iloc[i]

        if position == 0:
            # Grid entry (limit order)
            if rsi < 35 and bb_width < 0.05:
                entry_price = price  # Assumes limit order fills at the target price
                trade_value = (balance * position_size)
                fee = trade_value * fee_rate
                position = trade_value / entry_price
                balance -= (trade_value + fee)
                trade_log.append({'type': 'buy(grid)', 'price': entry_price, 'balance': balance, 'timestamp': df['timestamp'].iloc[i]})

            # Breakout entry (market order)
            elif rsi < 70 and price > prev_high:
                entry_price = price * (1 + slippage_pct)  # Apply slippage
                trade_value = (balance * position_size)
                fee = trade_value * fee_rate
                position = trade_value / entry_price
                balance -= (trade_value + fee)
                trade_log.append({'type': 'buy(breakout)', 'price': entry_price, 'balance': balance, 'timestamp': df['timestamp'].iloc[i]})
        else:
            # Exit condition (market order)
            if rsi > 80:
                exit_price = price * (1 - slippage_pct)  # Apply slippage
                trade_value = position * exit_price
                fee = trade_value * fee_rate
                balance += (trade_value - fee)
                trade_log.append({'type': 'sell', 'price': exit_price, 'balance': balance, 'timestamp': df['timestamp'].iloc[i]})
                position = 0

    # If still in a position at the end, exit at the last known price
    if position > 0:
        final_price = df['close'].iloc[-1] * (1 - slippage_pct)
        trade_value = position * final_price
        fee = trade_value * fee_rate
        balance += (trade_value - fee)
        trade_log.append({'type': 'final_exit', 'price': final_price, 'balance': balance, 'timestamp': df['timestamp'].iloc[-1]})

    return pd.DataFrame(trade_log), balance

def plot_performance(trades, df):
    plt.figure(figsize=(14, 6))
    plt.plot(df['timestamp'], df['close'], label='Price', alpha=0.5)

    buy_trades = trades[trades['type'].str.contains('buy')]
    sell_trades = trades[trades['type'].str.contains('sell|exit')]

    plt.scatter(buy_trades['timestamp'], buy_trades['price'], color='green', marker='^', s=100, label='Buy')
    plt.scatter(sell_trades['timestamp'], sell_trades['price'], color='red', marker='v', s=100, label='Sell')

    plt.title("Backtest Performance with Fees & Slippage")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.grid(True)
    plt.legend()
    plt.show()

if __name__ == "__main__":
    # --- Fetch data if not present ---
    symbol = "BTCUSDT"
    interval = Client.KLINE_INTERVAL_1HOUR
    csv_file = f"backtest/{symbol}_1h.csv"
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not os.path.exists(csv_file):
        fetch_binance_klines(symbol, interval, "1 Jan, 2022", None, csv_file, api_key, api_secret)
        time.sleep(1)
    df = load_data(csv_file)
    df = apply_indicators(df)
    # Run backtest with fees and slippage
    trades, final_balance = strategy_backtest(df, fee_rate=0.001, slippage_pct=0.0005)
    print(trades)
    print(f"💰 Final Balance (with fees & slippage): ${final_balance:.2f}")
    plot_performance(trades, df)