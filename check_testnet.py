import os
import time
from binance.client import Client
from dotenv import load_dotenv
import pandas as pd # Make sure pandas is installed (it should be from requirements.txt)

# Load environment variables from your .env file
load_dotenv()

# Get your Binance API keys from the environment
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

# --- IMPORTANT: Connect to the Testnet ---
# Initialize the client
client = Client(api_key, api_secret)

# Set the client to use the Testnet URL from your .env file
# This assumes you have BINANCE_TESTNET_BASE_URL set in your .env
client.API_URL = os.getenv("BINANCE_TESTNET_BASE_URL", "https://testnet.binance.vision/api")

# Synchronize time with Binance server before making any requests
server_time = client.get_server_time()
time_offset = server_time['serverTime'] - int(time.time() * 1000)
client.timestamp_offset = time_offset


print("Connecting to Binance Testnet...")

# --- 1. Get All Account Balances ---
try:
    account_info = client.get_account()
    balances = account_info.get('balances', [])
    
    print("\n--- Account Balances (Testnet) ---")
    for balance in balances:
        # Only show assets with a balance
        if float(balance['free']) > 0 or float(balance['locked']) > 0:
            print(f"- {balance['asset']}:")
            print(f"  Free:   {balance['free']}")
            print(f"  Locked: {balance['locked']}")

except Exception as e:
    print(f"\nError fetching account balance: {e}")


# --- 2. Get Trade History for a Specific Symbol ---
# Get the symbol from your .env file, defaulting to BTCUSDT
symbol = os.getenv("TRADE_SYMBOL", "BTCUSDT") 

try:
    # Fetch trades for the symbol
    trades = client.get_my_trades(symbol=symbol)
    
    print(f"\n--- Trade History for {symbol} (Testnet) ---")
    if not trades:
        print("No trades found for this symbol.")
    else:
        # Reverse the list to show the most recent trades first
        for trade in reversed(trades):
            trade_time = pd.to_datetime(trade['time'], unit='ms')
            side = 'BUY' if trade['isBuyer'] else 'SELL'
            print(f"- Time: {trade_time}, Side: {side}, Price: {trade['price']}, Quantity: {trade['qty']}, Commission: {trade['commission']} {trade['commissionAsset']}")

except Exception as e:
    print(f"\nError fetching trade history for {symbol}: {e}")
