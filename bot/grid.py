import logging
import asyncio
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC
from binance.exceptions import BinanceAPIException
from bot.trading_stats import LiveTradingStats
from bot.position_manager import PositionManager
from bot.exchange_info import format_quantity, get_min_notional

async def place_grid_orders(client: Client, symbol: str, base_qty: float, levels: int, step_pct: float, profit_target_pct: float, invalidation_pct: float):
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
        min_notional = get_min_notional(client, symbol)
        position_manager = PositionManager()
        tasks = []
        amount_per_level = base_qty / levels

        # Calculate the invalidation price
        last_buy_price = current_price * (1 - (levels * step_pct / 100))
        invalidation_price = last_buy_price * (1 - invalidation_pct / 100)

        for i in range(1, levels + 1):
            buy_price = current_price * (1 - (i * step_pct / 100))
            quantity = amount_per_level / buy_price

            # Check if the order value meets the minimum notional value
            if quantity * buy_price < min_notional:
                logging.error(f"Order value for grid level {i} is too low. Value: {quantity * buy_price:.4f}, Min Notional: {min_notional}")
                continue # Skip this grid level

            quantity_str = format_quantity(client, symbol, quantity)

            def create_and_log_order(p=buy_price, q=quantity_str):
                try:
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
                        'order': order
                    })
                    position_manager.open_position(symbol, float(p), float(q), 'buy', 'grid', invalidation_price=invalidation_price)
                    
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
                except BinanceAPIException as e:
                    logging.error(f"Failed to place grid order for {q} {symbol} at {p}: {e}")
                    return None

            task = loop.run_in_executor(
                None,
                create_and_log_order
            )
            tasks.append(task)
            logging.info(f"Creating grid buy order: {quantity_str} @ {buy_price}")

        if not tasks:
            logging.error("No grid orders were placed. Check your risk settings and account balance.")
            return

        results = await asyncio.gather(*tasks)
        successful_orders = [res for res in results if res is not None]
        logging.info(f"Successfully placed {len(successful_orders)} out of {len(tasks)} grid orders.")

    except Exception as e:
        logging.error(f"Grid laddering failed: {str(e)}")
