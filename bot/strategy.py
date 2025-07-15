from binance.client import Client
import pandas as pd
import logging
from typing import Optional
import requests # Import requests for ConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type # Import tenacity
from binance.exceptions import BinanceAPIException # Import BinanceAPIException
from ta.volatility import BollingerBands # Import BollingerBands

@retry(stop=stop_after_attempt(7), wait=wait_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type((requests.exceptions.ConnectionError, BinanceAPIException)))
def get_data(client: Client, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
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

def calculate_bollinger_bands(df: pd.DataFrame, window: int = 20, window_dev: float = 2.0) -> pd.DataFrame:
    bb_indicator = BollingerBands(close=df["close"], window=window, window_dev=window_dev)
    df['bb_bbm'] = bb_indicator.bollinger_mavg()
    df['bb_bbh'] = bb_indicator.bollinger_hband()
    df['bb_bbl'] = bb_indicator.bollinger_lband()
    return df

def apply_indicators(df: pd.DataFrame, atr_period: int = 14, bb_window: int = 20, bb_window_dev: float = 2.0, use_bollinger_bands: bool = False):
    df['RSI'] = calculate_rsi(df)
    df = calculate_macd(df) # This modifies df in place and returns it
    df['ATR'] = calculate_atr(df, period=atr_period)
    if use_bollinger_bands:
        df = calculate_bollinger_bands(df, window=bb_window, window_dev=bb_window_dev)
    return df

def generate_signal(rsi: float, macd: float, macd_signal: float, sentiment: float,
                    sentiment_threshold_positive: float, sentiment_threshold_negative: float,
                    base_rsi_oversold: float, base_rsi_overbought: float,
                    use_bollinger_bands: bool, bb_bbl: Optional[float], bb_bbh: Optional[float], current_close: float) -> Optional[str]:
    """
    Hybrid strategy: RSI < 30, MACD bullish crossover, and positive sentiment.
    Returns 'buy', 'sell', or None.
    """
    
    # Adjust RSI thresholds based on sentiment
    # Positive sentiment makes buy signals easier (higher oversold threshold)
    # Negative sentiment makes sell signals easier (lower overbought threshold)
    adjusted_rsi_oversold = base_rsi_oversold - (sentiment * 10) # Example: sentiment 0.5 -> 30 - 5 = 25
    adjusted_rsi_overbought = base_rsi_overbought - (sentiment * 10) # Example: sentiment 0.5 -> 70 - 5 = 65

    # Bullish conditions
    macd_cross_bullish = macd > macd_signal # Simplified for current candle comparison
    rsi_oversold_condition = rsi < adjusted_rsi_oversold
    sentiment_positive_condition = sentiment > sentiment_threshold_positive  # Use configurable threshold

    bollinger_buy_condition = True
    if use_bollinger_bands and bb_bbl is not None and current_close is not None:
        bollinger_buy_condition = current_close < bb_bbl # Price below lower band

    if macd_cross_bullish and rsi_oversold_condition and sentiment_positive_condition and bollinger_buy_condition:
        return 'buy'

    # Bearish conditions
    macd_cross_bearish = macd < macd_signal # Simplified for current candle comparison
    rsi_overbought_condition = rsi > adjusted_rsi_overbought
    sentiment_negative_condition = sentiment < sentiment_threshold_negative  # Use configurable threshold

    bollinger_sell_condition = True
    if use_bollinger_bands and bb_bbh is not None and current_close is not None:
        bollinger_sell_condition = current_close > bb_bbh # Price above upper band

    if macd_cross_bearish and rsi_overbought_condition and sentiment_negative_condition and bollinger_sell_condition:
        return 'sell'
        
    return None