import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import logging

def analyze_trades(trades_df: pd.DataFrame):
    """
    Performs detailed analysis on a DataFrame of trades.
    Assumes trades_df has at least 'type', 'price', 'quantity', 'balance', 'timestamp', and 'profit_loss' columns.
    'type' should indicate buy/sell and strategy (e.g., 'buy(breakout)', 'sell(breakout_sl)', 'sell(grid_tp)').
    """
    if trades_df.empty:
        logging.info("No trades to analyze.")
        return

    # Use the pre-calculated 'profit_loss' column directly
    trades_df['pnl'] = trades_df['profit_loss']

    # Identify winning and losing trades based on PnL
    winning_trades_pnl = trades_df[trades_df['pnl'] > 0]['pnl']
    losing_trades_pnl = trades_df[trades_df['pnl'] < 0]['pnl']

    total_trades = len(trades_df)
    winning_trades_count = len(winning_trades_pnl)
    losing_trades_count = len(losing_trades_pnl)

    # Basic Metrics
    win_rate = winning_trades_count / total_trades if total_trades > 0 else 0
    avg_win = winning_trades_pnl.mean() if winning_trades_count > 0 else 0
    avg_loss = losing_trades_pnl.mean() if losing_trades_count > 0 else 0
    gross_profit = winning_trades_pnl.sum()
    gross_loss = losing_trades_pnl.sum()
    profit_factor = abs(gross_profit / gross_loss) if gross_loss < 0 else float('inf')

    # Trade Streaks
    # This is a simplified streak calculation based on sequential PnL signs.
    # A more complex approach would track individual trade outcomes.
    streaks = []
    current_streak = 0
    current_streak_type = None # 'win' or 'loss'

    for pnl in trades_df['pnl']:
        if pnl > 0:
            if current_streak_type == 'win':
                current_streak += 1
            else:
                if current_streak_type is not None: streaks.append((current_streak_type, current_streak))
                current_streak = 1
                current_streak_type = 'win'
        elif pnl < 0:
            if current_streak_type == 'loss':
                current_streak -= 1 # Use negative for loss streak
            else:
                if current_streak_type is not None: streaks.append((current_streak_type, current_streak))
                current_streak = -1
                current_streak_type = 'loss'
        else:
            if current_streak_type is not None: streaks.append((current_streak_type, current_streak))
            current_streak = 0
            current_streak_type = None
    if current_streak_type is not None: streaks.append((current_streak_type, current_streak))

    longest_winning_streak = max([s[1] for s in streaks if s[0] == 'win'] or [0])
    longest_losing_streak = min([s[1] for s in streaks if s[0] == 'loss'] or [0]) * -1 # Convert to positive

    # Largest Win/Loss
    largest_win = winning_trades_pnl.max() if winning_trades_count > 0 else 0
    largest_loss = losing_trades_pnl.min() if losing_trades_count > 0 else 0

    logging.info("\n--- Detailed Trade Analysis ---")
    logging.info(f"Total Trades: {total_trades}")
    logging.info(f"Winning Trades: {winning_trades_count}")
    logging.info(f"Losing Trades: {losing_trades_count}")
    logging.info(f"Win Rate: {win_rate:.2%}")
    logging.info(f"Gross Profit: {gross_profit:.2f}")
    logging.info(f"Gross Loss: {gross_loss:.2f}")
    logging.info(f"Profit Factor: {profit_factor:.2f}")
    logging.info(f"Average Win: {avg_win:.2f}")
    logging.info(f"Average Loss: {avg_loss:.2f}")
    logging.info(f"Largest Win: {largest_win:.2f}")
    logging.info(f"Largest Loss: {largest_loss:.2f}")
    logging.info(f"Longest Winning Streak: {longest_winning_streak}")
    logging.info(f"Longest Losing Streak: {longest_losing_streak}")

    # Plot PnL Distribution
    if not trades_df.empty:
        plt.figure(figsize=(10, 6))
        plt.hist(trades_df['pnl'], bins=20, edgecolor='black')
        plt.title("Distribution of Trade PnL")
        plt.xlabel("Profit/Loss (USDT)")
        plt.ylabel("Frequency")
        plt.grid(True)
        plt.show()

if __name__ == "__main__":
    # This script is intended to be called by optimize_params.py after a study is complete.
    # It can also be used to analyze a trade log CSV directly.
    # Example: 
    # trades_df = pd.read_csv('backtest/optimization_results/best_trades_balance_12345.67.csv')
    # analyze_trades(trades_df)
    logging.info("This script is a module to be used by other parts of the application.")
