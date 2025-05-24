from binance.client import Client
from binance.enums import *

def place_grid_orders(client: Client, symbol: str, base_qty: float, levels: int = 3, step_pct: float = 1.0):
    """
    Places grid ladder buy orders below current price.
    """
    try:
        current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])

        for i in range(1, levels + 1):
            buy_price = current_price * (1 - (i * step_pct / 100))
            quantity = round(base_qty / current_price, 6)

            order = client.create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_LIMIT,
                quantity=quantity,
                price=str(round(buy_price, 2)),
                timeInForce=TIME_IN_FORCE_GTC
            )
            print(f"📉 Placed grid buy: {quantity} @ {buy_price}")
    except Exception as e:
        print("⚠️ Grid laddering failed:", e)
