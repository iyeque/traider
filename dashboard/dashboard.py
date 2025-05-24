import streamlit as st
import pandas as pd
import plotly.graph_objs as go
from ta.momentum import RSIIndicator
from bot.strategy import get_data  # You must have this function in strategy.py

st.set_page_config(layout="wide")
st.title("📊 Crypto Trading Bot Dashboard")

df = get_data('BTCUSDT', '1h', 200)
df['RSI'] = RSIIndicator(df['c'], window=14).rsi()

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df.index,
    open=df['o'],
    high=df['h'],
    low=df['l'],
    close=df['c'],
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
