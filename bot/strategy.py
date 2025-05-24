from binance.client import Client
from binance.enums import *

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
