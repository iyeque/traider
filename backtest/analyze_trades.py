import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import logging
import argparse
import os
import glob

def analyze_trades(trades_df: pd.DataFrame):
    """
    Performs detailed analysis on a DataFrame of trades from the new logger format.
    It analyzes trades with a status of 'CLOSED' to calculate profitability.
    """
    if trades_df.empty:
        logging.info("Trade log is empty. Nothing to analyze.")
        return

    # Support two formats:
    # 1) Live log format: columns include ['status', 'pnl'] (from OrderMonitor)
    # 2) Backtest format: columns include ['type', 'profit_loss'] (from backtest)

    if 'status' in trades_df.columns and 'pnl' in trades_df.columns:
        # A completed trade cycle is marked with the status 'CLOSED'
        closed_trades_df = trades_df[trades_df['status'] == 'CLOSED'].copy()
        if closed_trades_df.empty:
            logging.info("No closed trades found to analyze. (Waiting for positions to be closed). ")
            return
        pnl_series = pd.to_numeric(closed_trades_df['pnl'], errors='coerce').fillna(0)
    elif 'type' in trades_df.columns and 'profit_loss' in trades_df.columns:
        # Consider sells/exits as closed trades in backtest output
        type_series = trades_df['type'].astype(str)
        closed_mask = type_series.str.contains('sell|exit|invalidation', case=False, regex=True)
        closed_trades_df = trades_df[closed_mask].copy()
        if closed_trades_df.empty:
            logging.info("No sell/exit trades found to analyze in backtest output.")
            return
        pnl_series = pd.to_numeric(closed_trades_df['profit_loss'], errors='coerce').fillna(0)
        # Normalize for downstream usage
        closed_trades_df['pnl'] = pnl_series
    else:
        logging.info("Unrecognized trade log format. Expected columns ['status','pnl'] or ['type','profit_loss'].")
        return

    winning_trades_pnl = pnl_series[pnl_series > 0]
    losing_trades_pnl = pnl_series[pnl_series < 0]

    total_trades = len(pnl_series)
    winning_trades_count = len(winning_trades_pnl)
    losing_trades_count = len(losing_trades_pnl)

    # --- Calculate Metrics ---
    win_rate = winning_trades_count / total_trades if total_trades > 0 else 0
    avg_win = winning_trades_pnl.mean() if winning_trades_count > 0 else 0
    avg_loss = losing_trades_pnl.mean() if losing_trades_count > 0 else 0
    gross_profit = winning_trades_pnl.sum()
    gross_loss = losing_trades_pnl.sum()
    profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else float('inf')
    net_profit = gross_profit + gross_loss

    largest_win = winning_trades_pnl.max() if winning_trades_count > 0 else 0
    largest_loss = losing_trades_pnl.min() if losing_trades_count > 0 else 0

    # --- Print Analysis Summary ---
    logging.info("\n--- Trade Analysis Summary ---")
    logging.info(f"Total Closed Trades: {total_trades}")
    logging.info(f"Net Profit: {net_profit:.2f}")
    logging.info(f"Profit Factor: {profit_factor:.2f}")
    logging.info("---------------------------------")
    logging.info(f"Winning Trades: {winning_trades_count}")
    logging.info(f"Losing Trades: {losing_trades_count}")
    logging.info(f"Win Rate: {win_rate:.2%}")
    logging.info("---------------------------------")
    logging.info(f"Average Win: {avg_win:.2f}")
    logging.info(f"Average Loss: {avg_loss:.2f}")
    logging.info(f"Largest Win: {largest_win:.2f}")
    logging.info(f"Largest Loss: {largest_loss:.2f}")
    logging.info("---------------------------------")

    # --- Plot PnL Distribution ---
    if not closed_trades_df.empty:
        plt.figure(figsize=(10, 6))
        plt.hist(closed_trades_df['pnl'], bins=30, edgecolor='black', color='skyblue')
        plt.title("Distribution of Trade PnL", fontsize=16)
        plt.xlabel("Profit / Loss (USDT)", fontsize=12)
        plt.ylabel("Number of Trades", fontsize=12)
        plt.grid(axis='y', alpha=0.75)
        plt.axvline(x=0, color='r', linestyle='--')
        logging.info("Displaying PnL distribution plot...")
        plt.show()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser(description='Analyze a trade log file from the trading bot.')
    parser.add_argument(
        'filepath',
        type=str,
        nargs='?',
        default=None,
        help='Optional: Path to the trade log CSV file (e.g., live_trades.csv). If not provided, it looks for the latest backtest result.'
    )

    args = parser.parse_args()

    try:
        filepath_to_analyze = args.filepath
        
        # If no filepath is provided, default to old behavior for back-compatibility
        if filepath_to_analyze is None:
            logging.info("No file specified. Looking for latest backtest result...")
            results_dir = os.path.join("backtest", "optimization_results")
            if not os.path.exists(results_dir):
                logging.error(f"Default directory not found: {results_dir}")
                exit()
            list_of_files = glob.glob(os.path.join(results_dir, '*.csv'))
            if not list_of_files:
                logging.error(f"No trade log files found in {results_dir}")
                exit()
            filepath_to_analyze = max(list_of_files, key=os.path.getctime)

        if not os.path.exists(filepath_to_analyze):
            logging.error(f"File not found: {filepath_to_analyze}")
        else:
            logging.info(f"Analyzing trade log: {filepath_to_analyze}")
            trades_df = pd.read_csv(filepath_to_analyze)
            analyze_trades(trades_df)

    except Exception as e:
        logging.error(f"An error occurred during analysis: {e}", exc_info=True)