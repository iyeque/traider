import logging
import asyncio
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC
from bot.trading_stats import LiveTradingStats
from bot.position_manager import PositionManager
from bot.exchange_info import format_quantity

async def place_grid_orders(client: Client, symbol: str, base_qty: float, levels: int, step_pct: float, profit_target_pct: float):
    """
    Places grid ladder buy orders below current price asynchronously, and places corresponding sell (take-profit/stop-loss) orders.
    """
    try:
        loop = asyncio.get_event_loop()
        ticker_data = await loop.run_in_executor(
            None,
            lambda: client.get_symbol_ticker(symbol=symbol)
        )
        current_price = float(ticker_data['price'])
        position_manager = PositionManager()
        tasks = []
        amount_per_level = base_qty / levels

        for i in range(1, levels + 1):
            buy_price = current_price * (1 - (i * step_pct / 100))
            quantity = amount_per_level / buy_price
            quantity_str = format_quantity(client, symbol, quantity)

            def create_and_log_order(p=buy_price, q=quantity_str):
                order = client.create_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_LIMIT,
                    quantity=q,
                    price=str(round(p, 2)),
                    timeInForce=TIME_IN_FORCE_GTC
                )
                LiveTradingStats().log_trade({
                    'symbol': symbol,
                    'side': 'buy',
                    'quantity': q,
                    'order': order,
                    'profit': 0.0
                })
                position_manager.open_position(symbol, float(p), float(q), 'buy', 'grid')
                
                tp_price = float(p) * (1 + profit_target_pct / 100)
                client.create_order(
                    symbol=symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_LIMIT,
                    quantity=q,
                    price=str(round(tp_price, 2)),
                    timeInForce=TIME_IN_FORCE_GTC
                )
                return order

            task = loop.run_in_executor(
                None,
                create_and_log_order
            )
            tasks.append(task)
            logging.info(f"Creating grid buy order: {quantity_str} @ {buy_price}")

        await asyncio.gather(*tasks)
        logging.info(f"Successfully placed {levels} grid orders and corresponding sell orders")

    except Exception as e:
        logging.error(f"Grid laddering failed: {str(e)}")
        raise
