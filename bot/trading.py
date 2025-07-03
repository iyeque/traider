import logging
import asyncio
from binance.client import Client
from binance.enums import (
    SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC
)
from bot.trading_stats import LiveTradingStats
from bot.strategy import get_data, calculate_atr
from bot.exchange_info import format_quantity

def place_market_order_with_sl_tp(client: Client, symbol: str, side: str, amount_to_risk: float, rr_ratio: float, atr_period: int):
    try:
        df = get_data(client, symbol, '1m', limit=100) # Use 1m for recent price
        price = df['close'].iloc[-1]
        atr = calculate_atr(df, period=atr_period).iloc[-1]

        if side == 'buy':
            sl_price = price - (2 * atr)
            tp_price = price + (rr_ratio * (price - sl_price))
        else: # sell
            sl_price = price + (2 * atr)
            tp_price = price - (rr_ratio * (sl_price - price))

        quantity = amount_to_risk / (price - sl_price)
        quantity_str = format_quantity(client, symbol, quantity)

        # Place market order
        market_order = client.create_order(
            symbol=symbol,
            side=SIDE_BUY if side == 'buy' else SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=quantity_str
        )
        print(f"Market {side} order placed for {quantity_str} {symbol} at {price}")

        # Place OCO order for SL/TP
        client.create_oco_order(
            symbol=symbol,
            side=SIDE_SELL if side == 'buy' else SIDE_BUY,
            quantity=quantity_str,
            price=f'{tp_price:.2f}',
            stopPrice=f'{sl_price:.2f}',
            stopLimitPrice=f'{sl_price:.2f}',
            stopLimitTimeInForce=TIME_IN_FORCE_GTC
        )
        print(f"OCO order placed with TP at {tp_price:.2f} and SL at {sl_price:.2f}")

        LiveTradingStats().log_trade({
            'symbol': symbol,
            'side': side,
            'quantity': quantity_str,
            'order': market_order,
            'profit': 0.0
        })
        return market_order

    except Exception as e:
        logging.error(f"Failed to place market order with SL/TP: {e}")
        return None
