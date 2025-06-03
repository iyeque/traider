from dotenv import load_dotenv
import os

load_dotenv()

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
from binance.client import Client
from binance.enums import (
    SIDE_BUY,
    SIDE_SELL,
    ORDER_TYPE_MARKET
)

def place_market_order(client: Client, symbol: str, side: str, quantity: float):
    try:
        order = client.create_order(
            symbol=symbol,
            side=SIDE_BUY if side.lower() == 'buy' else SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )
        print(f"✅ {side.upper()} ORDER EXECUTED: {quantity} {symbol}")
        return order
    except Exception as e:
        print(f"❌ Order failed: {e}")
        return None
