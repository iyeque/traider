import os
import csv
from datetime import datetime
import threading

# Use a lock for thread-safe file writing
log_lock = threading.Lock()

def log_trade(trade_data: dict):
    """
    Logs a trade to the appropriate CSV file based on the environment.
    
    Args:
        trade_data (dict): A dictionary containing the trade details.
                           Expected keys: symbol, side, quantity, price,
                                          commission, commission_asset, pnl, status
    """
    log_file_name = "trade_log.csv" # Default filename in case of error
    try:
        # Determine the log file based on the Binance environment
        binance_env = os.getenv("BINANCE_ENV", "LIVE")
        log_file_name = 'testnet_trades.csv' if binance_env == 'TESTNET' else 'live_trades.csv'
        
        # Define the header for the CSV file
        header = ['timestamp', 'symbol', 'side', 'quantity', 'price', 'commission', 'commission_asset', 'pnl', 'status']
        
        with log_lock:
            # Check if the file exists to write the header
            file_exists = os.path.isfile(log_file_name)
            
            with open(log_file_name, 'a', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=header)
                
                if not file_exists:
                    writer.writeheader()
                
                # Add a timestamp to the trade data
                trade_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                writer.writerow(trade_data)

    except Exception as e:
        # If logging fails, we don't want to crash the bot. Print an error instead.
        print(f"[ERROR] Failed to log trade to {log_file_name}: {e}")

