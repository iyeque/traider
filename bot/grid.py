import logging
import asyncio
from binance import AsyncClient
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC
from binance.exceptions import BinanceAPIException
from bot.position_manager import PositionManager
from bot.exchange_info import format_quantity, get_min_notional
from bot.trade_logger import log_trade as log_trade_to_csv

async def place_grid_orders(client: AsyncClient, symbol: str, base_qty: float, levels: int, step_pct: float, profit_target_pct: float, invalidation_pct: float) -> bool:
    try:
        loop = asyncio.get_event_loop()
        ticker_data = await client.get_symbol_ticker(symbol=symbol)
        current_price = float(ticker_data['price'])
        min_notional = await get_min_notional(client, symbol)

        # Ensure base_qty is sufficient for at least one level to meet min_notional
        if base_qty < min_notional * levels:
            logging.error(f"Base quantity ({base_qty:.4f}) is too low for {levels} grid levels with a minimum notional of {min_notional:.4f} per level. Consider increasing base_qty or decreasing levels.")
            return False

        position_manager = PositionManager() # Get singleton instance
        tasks = []
        amount_per_level = base_qty / levels

        last_buy_price = current_price * (1 - (levels * step_pct / 100))
        invalidation_price = last_buy_price * (1 - invalidation_pct / 100)

        for i in range(1, levels + 1):
            buy_price = current_price * (1 - (i * step_pct / 100))
            quantity = amount_per_level / buy_price

            if quantity * buy_price < min_notional:
                logging.error(f"Order value for grid level {i} is too low. Value: {quantity * buy_price:.4f}, Min Notional: {min_notional}")
                continue

            quantity_str = await format_quantity(client, symbol, quantity)

            async def create_and_log_order(p=buy_price, q=quantity_str):
                try:
                    buy_order = await client.create_order(
                        symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_LIMIT,
                        quantity=q, price=str(round(p, 2)), timeInForce=TIME_IN_FORCE_GTC
                    )
                    log_trade_to_csv({
                        'symbol': symbol, 'side': 'buy', 'quantity': q, 'price': p,
                        'commission': 0, 'commission_asset': 'N/A', 'pnl': 0,
                        'status': 'PLACED'
                    })

                    tp_price = float(p) * (1 + profit_target_pct / 100)
                    tp_order = await client.create_order(
                        symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_LIMIT,
                        quantity=q, price=str(round(tp_price, 2)), timeInForce=TIME_IN_FORCE_GTC
                    )
                    log_trade_to_csv({
                        'symbol': symbol, 'side': 'sell', 'quantity': q, 'price': tp_price,
                        'commission': 0, 'commission_asset': 'N/A', 'pnl': 0,
                        'status': 'PLACED_TP'
                    })

                    position_manager.open_position(
                        symbol=symbol, order_id=str(buy_order['orderId']), entry_price=p, 
                        quantity=float(q), side='buy', strategy='grid',
                        exit_order_ids=[str(tp_order['orderId'])], 
                        invalidation_price=invalidation_price
                    )
                    logging.info(f"Grid position opened in manager for order {buy_order['orderId']} with TP order {tp_order['orderId']}")

                    return buy_order
                except BinanceAPIException as e:
                    logging.error(f"Failed to place grid order for {q} {symbol} at {p}: {e}")
                    return None

            task = asyncio.create_task(create_and_log_order())
            tasks.append(task)
            logging.info(f"Creating grid buy order: {quantity_str} @ {buy_price}")

        if not tasks:
            logging.error("No grid orders were placed. Check your risk settings and account balance.")
            return False

        results = await asyncio.gather(*tasks)
        successful_orders = [res for res in results if res is not None]
        logging.info(f"Successfully placed {len(successful_orders)} out of {len(tasks)} grid orders.")
        return True

    except Exception as e:
        logging.error(f"Grid laddering failed: {str(e)}", exc_info=True)
        return False
