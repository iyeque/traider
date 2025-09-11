import logging
from typing import Dict, Any, Optional, Union, Tuple, List, cast
import math
from binance.client import Client

def get_symbol_info_sync(client: Client, symbol: str) -> Dict[str, Any]:
    """Get symbol information synchronously for backtesting.
    
    Args:
        client: Binance Client instance
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        
    Returns:
        Dictionary containing symbol information
    """
    try:
        exchange_info = client.get_exchange_info()
        for s in exchange_info['symbols']:
            if s['symbol'] == symbol:
                return s
        logging.error(f"Symbol {symbol} not found in exchange info")
        return {}
    except Exception as e:
        logging.error(f"Error getting symbol info: {e}")
        return {}

def get_min_notional_sync(client: Client, symbol: str) -> float:
    """Get minimum notional value for a symbol synchronously.
    
    Args:
        client: Binance Client instance
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        
    Returns:
        Minimum notional value as float
    """
    try:
        symbol_info = get_symbol_info_sync(client, symbol)
        if not symbol_info:
            logging.warning(f"Symbol info not found for {symbol}, using default min notional of 10.0")
            return 10.0
            
        for filter_item in symbol_info.get('filters', []):
            # Check for NOTIONAL filter type
            if filter_item.get('filterType') == 'NOTIONAL':
                return float(filter_item.get('minNotional', 10.0))
            # Check for MIN_NOTIONAL filter type (older API versions)
            elif filter_item.get('filterType') == 'MIN_NOTIONAL':
                return float(filter_item.get('minNotional', 10.0))
                
        logging.warning(f"MIN_NOTIONAL filter not found for {symbol}, using default of 10.0")
        return 10.0
    except Exception as e:
        logging.error(f"Error getting min notional: {e}")
        return 10.0

def format_quantity_sync(client: Client, symbol: str, quantity: float) -> float:
    """Format quantity according to symbol's LOT_SIZE filter synchronously.
    
    Args:
        client: Binance Client instance
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        quantity: Original quantity
        
    Returns:
        Formatted quantity as float
    """
    try:
        symbol_info = get_symbol_info_sync(client, symbol)
        if not symbol_info:
            logging.warning(f"Symbol info not found for {symbol}, rounding to 8 decimal places")
            return float(f"{quantity:.8f}")
            
        for filter_item in symbol_info.get('filters', []):
            if filter_item.get('filterType') == 'LOT_SIZE':
                step_size = float(filter_item.get('stepSize', 0.00000001))
                precision = int(round(-math.log10(step_size)))
                quantity = math.floor(quantity * 10**precision) / 10**precision
                return quantity
                
        logging.warning(f"LOT_SIZE filter not found for {symbol}, rounding to 8 decimal places")
        return float(f"{quantity:.8f}")
    except Exception as e:
        logging.error(f"Error formatting quantity: {e}")
        return float(f"{quantity:.8f}")