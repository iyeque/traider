import asyncio
import logging
from binance import AsyncClient
from bot.position_manager import PositionManager
from bot.trade_logger import log_trade
from bot.trading_stats import LiveTradingStats
from datetime import datetime

class OrderMonitor:
    def __init__(self, client: AsyncClient):
        self.client = client
        self.position_manager = PositionManager()
        self.last_trade_ids: dict[str, int] = {} # key: symbol, value: last trade id

    async def start(self, interval_seconds: int = 15):
        logging.info("Order monitor started.")
        while True:
            await self.check_for_filled_orders()
            await asyncio.sleep(interval_seconds)

    async def check_for_filled_orders(self):
        open_positions = self.position_manager.get_open_positions()
        if not open_positions:
            return

        symbols = {pos['symbol'] for pos in open_positions}

        for symbol in symbols:
            try:
                from_id = self.last_trade_ids.get(symbol, 0)
                # Using limit=50 to avoid fetching too many trades at once
                trades = await self.client.get_my_trades(symbol=symbol, fromId=from_id, limit=50)

                if not trades:
                    continue
                
                logging.info(f"Found {len(trades)} new trade(s) for {symbol}.")

                for trade in trades:
                    trade_id = trade['id']
                    order_id = str(trade['orderId'])
                    
                    # A closing trade will have the opposite side of the entry trade
                    pos = self.position_manager.find_position_by_exit_order_id(order_id)

                    if pos and pos['open'] and trade['side'].lower() != pos['side'].lower():
                        logging.info(f"Detected closing trade for position {pos['order_id']} (Order ID: {order_id})")
                        
                        exit_price = float(trade['price'])
                        realized_pnl = self.position_manager.close_position(symbol, pos['order_id'], exit_price)

                        if realized_pnl is not None:
                            trade_data = {
                                'symbol': symbol,
                                'side': trade['side'].lower(),
                                'quantity': float(trade['qty']),
                                'price': exit_price,
                                'commission': float(trade['commission']),
                                'commission_asset': trade['commissionAsset'],
                                'pnl': realized_pnl,
                                'status': 'CLOSED',
                                'timestamp': datetime.now().isoformat() # Add timestamp
                            }
                            log_trade(trade_data)
                            LiveTradingStats().log_trade(trade_data)
                            logging.info(f"Position {pos['order_id']} closed. Realized PnL: {realized_pnl:.2f}")

                    # Update the last trade ID processed for this symbol
                    if trade_id > self.last_trade_ids.get(symbol, 0):
                         self.last_trade_ids[symbol] = trade_id

            except Exception as e:
                logging.error(f"Error checking filled orders for {symbol}: {e}")
