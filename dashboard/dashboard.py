import streamlit as st
import pandas as pd
import plotly.graph_objs as go
from ta.momentum import RSIIndicator
import sys
from pathlib import Path
from binance.client import Client

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os

load_dotenv()
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
from bot.strategy import get_data

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
df = get_data(client, 'BTCUSDT', Client.KLINE_INTERVAL_1HOUR, 200)

if df is not None:
    # Convert timestamp to datetime index
    df.index = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Calculate RSI - ensure close_series remains a Series after conversion
    close_series = pd.Series(pd.to_numeric(df['close']))
    df['RSI'] = RSIIndicator(close=close_series, window=14).rsi()

    # Create figure
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Candlesticks'
    ))

    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['RSI'],
        mode='lines',
        name='RSI (14)',
        yaxis='y2',
        line=dict(color='blue')
    ))

    fig.update_layout(
        title="BTC/USDT 1H + RSI",
        yaxis=dict(title='Price'),
        yaxis2=dict(title='RSI', overlaying='y', side='right'),
        height=600,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Failed to fetch data from Binance. Please check your API keys and internet connection.")
