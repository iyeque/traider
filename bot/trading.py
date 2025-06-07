import logging
import asyncio
from binance.client import Client
from binance.enums import (
    SIDE_BUY,
    SIDE_SELL,
    ORDER_TYPE_MARKET
)

async def place_market_order(client: Client, symbol: str, side: str, quantity: float):
    try:
        # Execute the order in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        order = await loop.run_in_executor(
            None,
            lambda: client.create_order(
                symbol=symbol,
                side=SIDE_BUY if side.lower() == 'buy' else SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
        )
        logging.info(f"✅ {side.upper()} ORDER EXECUTED: {quantity} {symbol}")
        return order
    except Exception as e:
        logging.error(f"❌ Order failed: {str(e)}")
        return None
