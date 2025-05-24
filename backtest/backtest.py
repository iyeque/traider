import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
import matplotlib.pyplot as plt

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

def strategy_backtest(df, starting_balance=10000, position_size=0.05):
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
            if rsi < 35 and bb_width < 0.05:
                # Grid entry
                entry_price = price
                position = (balance * position_size) / price
                balance -= position * price
                trade_log.append({'type': 'buy(grid)', 'price': price, 'balance': balance, 'timestamp': df['timestamp'].iloc[i]})

            elif rsi < 70 and price > prev_high:
                # Breakout entry
                entry_price = price
                position = (balance * position_size) / price
                balance -= position * price
                trade_log.append({'type': 'buy(breakout)', 'price': price, 'balance': balance, 'timestamp': df['timestamp'].iloc[i]})
        else:
            if rsi > 80:
                balance += position * price
                trade_log.append({'type': 'sell', 'price': price, 'balance': balance, 'timestamp': df['timestamp'].iloc[i]})
                position = 0

    if position > 0:
        balance += position * df['close'].iloc[-1]
        trade_log.append({'type': 'final_exit', 'price': df['close'].iloc[-1], 'balance': balance, 'timestamp': df['timestamp'].iloc[-1]})

    return pd.DataFrame(trade_log), balance

def plot_performance(trades, df):
    plt.figure(figsize=(14, 6))
    plt.plot(df['timestamp'], df['close'], label='Price')

    for _, row in trades.iterrows():
        color = 'green' if 'buy' in row['type'] else 'red'
        marker = '^' if 'buy' in row['type'] else 'v'
        plt.scatter(row['timestamp'], row['price'], color=color, marker=marker, s=100, label=row['type'])

    plt.title("Trade Entries and Exits")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.grid()
    plt.legend(loc='upper left')
    plt.show()

if __name__ == "__main__":
    df = load_data("backtest/BTCUSDT_1h.csv")  # Add your historical CSV file
    df = apply_indicators(df)
    trades, final_balance = strategy_backtest(df)
    print(trades)
    print(f"💰 Final Balance: ${final_balance:.2f}")
    plot_performance(trades, df)
