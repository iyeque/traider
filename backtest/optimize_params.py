import pandas as pd
import os
import sys
import logging
import optuna  # Import Optuna
from analyze_trades import analyze_trades

# Add the parent directory to the sys.path to allow importing backtest.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import backtest
from binance.client import Client

# Configure logging for optimization script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def objective(trial, df, historical_sentiment_csv, client):  # Pass data as arguments
    """Objective function for Optuna to optimize."""
    # --- Define Parameter Search Space using Optuna ---
    atr_period = trial.suggest_int('atr_period', 10, 20)
    atr_trend_threshold = trial.suggest_float('atr_trend_threshold', 0.01, 0.03, step=0.01)
    breakout_rr_ratio = trial.suggest_float('breakout_rr_ratio', 2.0, 3.5, step=0.5)
    grid_levels = trial.suggest_int('grid_levels', 3, 5)
    grid_step_percent = trial.suggest_float('grid_step_percent', 0.5, 1.5, step=0.5)
    grid_profit_target_percent = trial.suggest_float('grid_profit_target_percent', 1.0, 2.0, step=0.5)
    grid_invalidation_percent = trial.suggest_float('grid_invalidation_percent', 1.5, 2.5, step=0.5)
    risk_per_trade_percent = trial.suggest_float('risk_per_trade_percent', 1.0, 10.0, step=1.0)
    sentiment_threshold_positive = trial.suggest_float('sentiment_threshold_positive', 0.0, 0.2, step=0.1)
    sentiment_threshold_negative = trial.suggest_float('sentiment_threshold_negative', -0.2, 0.0, step=0.1)
    volume_factor = trial.suggest_float('volume_factor', 1e-7, 1e-5, log=True)
    latency_seconds = trial.suggest_categorical('latency_seconds', [0, 60, 300])
    max_drawdown_percent = trial.suggest_categorical('max_drawdown_percent', [10.0, 20.0, 30.0])
    max_trades = trial.suggest_categorical('max_trades', [0, 50, 100])
    sentiment_sizing_multiplier = trial.suggest_float('sentiment_sizing_multiplier', 0.0, 1.0, step=0.25)
    base_rsi_oversold = trial.suggest_int('base_rsi_oversold', 20, 40)
    base_rsi_overbought = trial.suggest_int('base_rsi_overbought', 60, 80)
    use_bollinger_bands = trial.suggest_categorical('use_bollinger_bands', [True, False])
    bb_window = trial.suggest_int('bb_window', 15, 25) if use_bollinger_bands else 20
    bb_window_dev = trial.suggest_float('bb_window_dev', 1.5, 2.5, step=0.5) if use_bollinger_bands else 2.0

    try:
        # Run the backtest with the suggested parameters
        trades, final_balance, metrics = backtest.strategy_backtest(
            client,
            df,
            starting_balance=10000,
            fee_rate=0.001,
            base_slippage_pct=0.0005,
            volume_factor=volume_factor,
            latency_seconds=latency_seconds,
            max_drawdown_percent=max_drawdown_percent,
            max_trades=max_trades,
            sentiment_sizing_multiplier=sentiment_sizing_multiplier,
            atr_period=atr_period,
            atr_trend_threshold=atr_trend_threshold,
            breakout_rr_ratio=breakout_rr_ratio,
            grid_levels=grid_levels,
            grid_step_percent=grid_step_percent,
            grid_profit_target_percent=grid_profit_target_percent,
            grid_invalidation_percent=grid_invalidation_percent,
            risk_per_trade_percent=risk_per_trade_percent,
            trade_mode='PERCENTAGE',
            fixed_trade_amount_usdt=5.0,
            sentiment_threshold_positive=sentiment_threshold_positive,
            sentiment_threshold_negative=sentiment_threshold_negative,
            base_rsi_oversold=base_rsi_oversold,
            base_rsi_overbought=base_rsi_overbought,
            use_bollinger_bands=use_bollinger_bands,
            bb_window=bb_window,
            bb_window_dev=bb_window_dev,
            sentiment_csv_file=historical_sentiment_csv,
            symbol="BTCUSDT"
        )
        return final_balance
    except Exception as e:
        logging.error(f"Error during Optuna trial {trial.number} with params {trial.params}: {e}")
        raise


from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":
    # Create Binance client
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    client = Client(api_key, api_secret)
    # --- Load Data Once ---
    symbol = os.getenv("TRADE_SYMBOL", "BTCUSDT")
    interval = "1h"
    csv_file = f"backtest/{symbol}_{interval}.csv"

    if not os.path.exists(csv_file):
        logging.error(f"Historical data not found at {csv_file}. Please run backtest.py first to generate it.")
        sys.exit(1)  # Exit if data is missing

    df = backtest.load_data(csv_file)

    historical_sentiment_csv = "data_acquisition/historical_sentiment.csv"
    if not os.path.exists(historical_sentiment_csv):
        logging.warning(f"Historical sentiment data not found at {historical_sentiment_csv}. Sentiment will be neutral.")

    # --- Run Optimization ---
    study = optuna.create_study(direction='maximize')
    logging.info("Starting Optuna optimization...")
    # Use a lambda function to pass additional arguments to the objective
    study.optimize(lambda trial: objective(trial, df, historical_sentiment_csv, client), n_trials=100)

    # --- Print Best Results ---
    logging.info("\n--- Optuna Optimization Finished ---")
    logging.info("Best trial parameters:")
    best_params = study.best_trial.params
    for key, value in best_params.items():
        logging.info(f"  {key}: {value}")
    logging.info(f"Best final balance: ${study.best_value:.2f}")

    # --- Re-run and Analyze the Best Trial ---
    logging.info("\n--- Re-running backtest with best parameters to generate analysis ---")

    best_trades_df, final_balance, metrics = backtest.strategy_backtest(
        client,
        df,
        starting_balance=10000,
        fee_rate=0.001,
        base_slippage_pct=0.0005,
        trade_mode='PERCENTAGE',
        fixed_trade_amount_usdt=5.0,
        sentiment_csv_file=historical_sentiment_csv,
        symbol=symbol,
        **best_params
    )

    # --- Save the Best Trades ---
    output_dir = "backtest/optimization_results"
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"best_trades_balance_{final_balance:.2f}.csv")
    best_trades_df.to_csv(filename, index=False)
    logging.info(f"Saved trades from best trial to {filename}")

    # --- Perform Detailed Analysis ---
    logging.info("\n--- Analysis of Best Trial ---")
    analyze_trades(best_trades_df)