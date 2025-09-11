import logging
from datetime import datetime
from binance import AsyncClient
from binance.enums import (
    SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC
)
from bot.strategy import get_data, calculate_atr
from bot.exchange_info import format_quantity
from bot.trade_logger import log_trade as log_trade_to_csv
from bot.position_manager import PositionManager
from typing import Optional, Dict, Any
from bot.trading_stats import LiveTradingStats

def calculate_trade_size(balance: float, trade_mode: str, risk_per_trade_percent: float, current_sentiment: float, fixed_trade_amount_usdt: float = 5.0, sentiment_sizing_multiplier: float = 0.0) -> float:
    base_amount = 0
    if trade_mode == 'FIXED':
        base_amount = fixed_trade_amount_usdt
    else: # PERCENTAGE mode
        calculated_amount = balance * (risk_per_trade_percent / 100)
        base_amount = max(calculated_amount, fixed_trade_amount_usdt)
    
    adjusted_amount = base_amount * (1 + current_sentiment * sentiment_sizing_multiplier)
    return max(adjusted_amount, fixed_trade_amount_usdt)

async def place_market_order_with_sl_tp(client: AsyncClient, symbol: str, side: str, amount_to_risk: float, rr_ratio: float, atr_period: int):
    try:
        df = await get_data(client, symbol, '1m', limit=100)
        price = df['close'].iloc[-1]
        atr = calculate_atr(df, period=atr_period).iloc[-1]

        if side == 'buy':
            sl_price = price - (2 * atr)
            tp_price = price + (rr_ratio * (price - sl_price))
        else: # sell
            sl_price = price + (2 * atr)
            tp_price = price - (rr_ratio * (sl_price - price))

        quantity = amount_to_risk / abs(price - sl_price)
        quantity_str = format_quantity(client, symbol, quantity)

        market_order = await client.create_order(
            symbol=symbol,
            side=SIDE_BUY if side == 'buy' else SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=quantity_str
        )
        logging.info(f"Market {side} order response: {market_order}")

        fills = market_order.get('fills', [])
        if not fills:
            logging.error("Market order did not fill. Cannot proceed.")
            return None

        total_qty = sum(float(f['qty']) for f in fills)
        total_commission = sum(float(f['commission']) for f in fills)
        commission_asset = fills[0]['commissionAsset']
        avg_price = sum(float(f['price']) * float(f['qty']) for f in fills) / total_qty
        entry_order_id = str(market_order['orderId'])

        trade_data = {
            'symbol': symbol, 'side': side, 'quantity': total_qty, 'price': avg_price,
            'commission': total_commission, 'commission_asset': commission_asset,
            'pnl': 0, 'status': 'FILLED', 'timestamp': datetime.now().isoformat() # Add timestamp
        }
        log_trade_to_csv(trade_data)
        LiveTradingStats().log_trade(trade_data)
        logging.info(f"Market {side} order for {total_qty} {symbol} at avg price {avg_price} logged.")

        oco_order = await client.create_oco_order(
            symbol=symbol,
            side=SIDE_SELL if side == 'buy' else SIDE_BUY,
            quantity=quantity_str,
            price=f'{tp_price:.2f}',
            stopPrice=f'{sl_price:.2f}',
            stopLimitPrice=f'{sl_price:.2f}',
            stopLimitTimeInForce=TIME_IN_FORCE_GTC
        )
        logging.info(f"OCO order placed with TP at {tp_price:.2f} and SL at {sl_price:.2f}")
        
        exit_order_ids = [str(report['orderId']) for report in oco_order.get('orderReports', [])]

        position_manager = PositionManager()
        position_manager.open_position(
            symbol=symbol, order_id=entry_order_id, entry_price=avg_price,
            quantity=total_qty, side=side, strategy='breakout',
            exit_order_ids=exit_order_ids
        )
        logging.info(f"Position opened in manager for order {entry_order_id} with exit orders {exit_order_ids}")

        return market_order

    except Exception as e:
        logging.error(f"Failed to place market order with SL/TP: {e}", exc_info=True)
        return None

async def place_limit_order(client: AsyncClient, symbol: str, side: str, quantity: float, price: float) -> Optional[Dict[str, Any]]:
    # This function is not currently used by the main strategies but is kept for potential future use.
    try:
        quantity_str = format_quantity(client, symbol, quantity)
        order = await client.create_order(
            symbol=symbol,
            side=SIDE_BUY if side == 'buy' else SIDE_SELL,
            type=ORDER_TYPE_LIMIT,
            quantity=quantity_str,
            price=f'{price:.2f}',
            timeInForce=TIME_IN_FORCE_GTC
        )
        logging.info(f"Limit {side} order placed for {quantity_str} {symbol} at {price}")
        trade_data = {
            'symbol': symbol, 'side': side, 'quantity': quantity, 'price': price,
            'commission': 0, 'commission_asset': 'N/A', 'pnl': 0, 'status': 'PLACED', 'timestamp': datetime.now().isoformat() # Add timestamp
        }
        log_trade_to_csv(trade_data)
        LiveTradingStats().log_trade(trade_data)
        return order
    except Exception as e:
        logging.error(f"Failed to place limit order: {e}")
        return None
