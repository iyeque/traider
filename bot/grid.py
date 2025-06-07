import logging
import asyncio
from binance.client import Client
from binance.enums import SIDE_BUY, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC

async def place_grid_orders(client: Client, symbol: str, base_qty: float, levels: int = 3, step_pct: float = 1.0):
    """
    Places grid ladder buy orders below current price asynchronously.
    """
    try:
        loop = asyncio.get_event_loop()
        # Get current price in a non-blocking way
        ticker_data = await loop.run_in_executor(
            None,
            lambda: client.get_symbol_ticker(symbol=symbol)
        )
        current_price = float(ticker_data['price'])

        tasks = []
        for i in range(1, levels + 1):
            buy_price = current_price * (1 - (i * step_pct / 100))
            quantity = round(base_qty / current_price, 6)

            # Create task for each order
            task = loop.run_in_executor(
                None,
                lambda p=buy_price, q=quantity: client.create_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_LIMIT,
                    quantity=q,
                    price=str(round(p, 2)),
                    timeInForce=TIME_IN_FORCE_GTC
                )
            )
            tasks.append(task)
            logging.info(f"📉 Creating grid buy order: {quantity} @ {buy_price}")

        # Wait for all orders to complete
        await asyncio.gather(*tasks)
        logging.info(f"✅ Successfully placed {levels} grid orders")

    except Exception as e:
        logging.error(f"⚠️ Grid laddering failed: {str(e)}")
        raise
