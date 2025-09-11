import logging
import math
from binance import AsyncClient
from functools import lru_cache
from math import floor

async def get_symbol_info(client: AsyncClient, symbol: str):
    try:
        return await client.get_symbol_info(symbol)
    except Exception as e:
        logging.error(f"Could not retrieve symbol info for {symbol}: {e}")
        return None

async def get_min_notional(client: AsyncClient, symbol: str) -> float:
    info = await get_symbol_info(client, symbol)
    if not info:
        return 0.0
    
    # Check for the modern 'NOTIONAL' filter first, then fallback to 'MIN_NOTIONAL'
    notional_filter = next((f for f in info['filters'] if f['filterType'] == 'NOTIONAL'), None)
    if notional_filter:
        return float(notional_filter.get('minNotional', 0.0))

    min_notional_filter = next((f for f in info['filters'] if f['filterType'] == 'MIN_NOTIONAL'), None)
    if min_notional_filter:
        return float(min_notional_filter.get('minNotional', 0.0))
        
    return 0.0

async def format_quantity(client: AsyncClient, symbol: str, quantity: float) -> str:
    info = await get_symbol_info(client, symbol)
    if not info:
        return f"{quantity:.8f}"

    lot_size_filter = next((f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
    if not lot_size_filter:
        return f"{quantity:.8f}"

    step_size = float(lot_size_filter['stepSize'])
    precision = int(round(-math.log10(step_size), 0))
    
    # Floor the quantity to the required precision
    factor = 10**precision
    floored_quantity = floor(quantity * factor) / factor
    
    formatted_quantity = f"{floored_quantity:.{precision}f}"
    return formatted_quantity
