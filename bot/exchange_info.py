import logging
import math
from binance.client import Client
from functools import lru_cache

@lru_cache(maxsize=128)
def get_symbol_info(client: Client, symbol: str):
    try:
        return client.get_symbol_info(symbol)
    except Exception as e:
        logging.error(f"Could not retrieve symbol info for {symbol}: {e}")
        return None

def format_quantity(client: Client, symbol: str, quantity: float) -> str:
    info = get_symbol_info(client, symbol)
    if not info:
        return f"{quantity:.8f}"  # Fallback

    lot_size_filter = next((f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
    if not lot_size_filter:
        return f"{quantity:.8f}"

    step_size = float(lot_size_filter['stepSize'])
    precision = int(round(-math.log10(step_size), 0))
    
    formatted_quantity = f"{quantity:.{precision}f}"
    return formatted_quantity
