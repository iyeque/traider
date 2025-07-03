from binance.client import Client
import pandas as pd
import logging
from typing import Optional

def get_data(client: Client, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    columns = [
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'num_trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ]
    df = pd.DataFrame(klines, columns=columns)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col])
    return df

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    df['macd'] = macd
    df['macd_signal'] = signal
    return df

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def generate_signal(df: pd.DataFrame, sentiment: float) -> Optional[str]:
    """
    Hybrid strategy: RSI < 30, MACD bullish crossover, and positive sentiment.
    Returns 'buy', 'sell', or None.
    """
    df = calculate_macd(df)
    df['rsi'] = calculate_rsi(df)
    if len(df) < 26:
        logging.warning("Not enough data for MACD/RSI calculation.")
        return None
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Bullish conditions
    macd_cross_bullish = prev['macd'] < prev['macd_signal'] and latest['macd'] > latest['macd_signal']
    rsi_oversold = latest['rsi'] < 30
    sentiment_positive = sentiment > 0

    if macd_cross_bullish and rsi_oversold and sentiment_positive:
        return 'buy'

    # Bearish conditions
    macd_cross_bearish = prev['macd'] > prev['macd_signal'] and latest['macd'] < latest['macd_signal']
    rsi_overbought = latest['rsi'] > 70
    sentiment_negative = sentiment < 0

    if macd_cross_bearish and rsi_overbought and sentiment_negative:
        return 'sell'
        
    return None
