#!/usr/bin/env python3
"""Per-symbol Optuna tuning for Traider, exporting best params to the Cloudflare port.

Uses the EXACT 18-parameter search space from backtest/optimize_params.py and
the real backtest/strategy_backtest() on the checked-in hourly CSVs plus
historical_sentiment.csv. No credentials needed: the Binance client is used
only for public get_exchange_info() (LOT_SIZE / MIN_NOTIONAL filters).

Run from anywhere:
    python3 backtest/run_per_symbol.py --trials 25 \
        --out cloudflare/src/tuned_params.json
"""

import argparse
import datetime
import json
import logging
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import optuna
from binance.client import Client

from backtest import load_data, strategy_backtest

optuna.logging.set_verbosity(optuna.logging.WARNING)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


def objective(trial, df, client, symbol, sentiment_csv):
    # --- identical search space to backtest/optimize_params.py:objective ---
    params = {
        "atr_period": trial.suggest_int("atr_period", 10, 20),
        "atr_trend_threshold": trial.suggest_float("atr_trend_threshold", 0.01, 0.03, step=0.01),
        "breakout_rr_ratio": trial.suggest_float("breakout_rr_ratio", 2.0, 3.5, step=0.5),
        "grid_levels": trial.suggest_int("grid_levels", 3, 5),
        "grid_step_percent": trial.suggest_float("grid_step_percent", 0.5, 1.5, step=0.5),
        "grid_profit_target_percent": trial.suggest_float("grid_profit_target_percent", 1.0, 2.0, step=0.5),
        "grid_invalidation_percent": trial.suggest_float("grid_invalidation_percent", 1.5, 2.5, step=0.5),
        "risk_per_trade_percent": trial.suggest_float("risk_per_trade_percent", 1.0, 10.0, step=1.0),
        "sentiment_threshold_positive": trial.suggest_float("sentiment_threshold_positive", 0.0, 0.2, step=0.1),
        "sentiment_threshold_negative": trial.suggest_float("sentiment_threshold_negative", -0.2, 0.0, step=0.1),
        "volume_factor": trial.suggest_float("volume_factor", 1e-7, 1e-5, log=True),
        "latency_seconds": trial.suggest_categorical("latency_seconds", [0, 60, 300]),
        "max_drawdown_percent": trial.suggest_categorical("max_drawdown_percent", [10.0, 20.0, 30.0]),
        "max_trades": trial.suggest_categorical("max_trades", [0, 50, 100]),
        "sentiment_sizing_multiplier": trial.suggest_float("sentiment_sizing_multiplier", 0.0, 1.0, step=0.25),
        "base_rsi_oversold": trial.suggest_int("base_rsi_oversold", 20, 40),
        "base_rsi_overbought": trial.suggest_int("base_rsi_overbought", 60, 80),
        "use_bollinger_bands": trial.suggest_categorical("use_bollinger_bands", [True, False]),
    }
    params["bb_window"] = trial.suggest_int("bb_window", 15, 25) if params["use_bollinger_bands"] else 20
    params["bb_window_dev"] = trial.suggest_float("bb_window_dev", 1.5, 2.5, step=0.5) if params["use_bollinger_bands"] else 2.0

    _, final_balance, _ = run_backtest(df, client, symbol, sentiment_csv, params)
    return final_balance


def run_backtest(df, client, symbol, sentiment_csv, params):
    return strategy_backtest(
        client,
        df,
        starting_balance=10000,
        fee_rate=0.001,
        base_slippage_pct=0.0005,
        volume_factor=params["volume_factor"],
        latency_seconds=params["latency_seconds"],
        max_drawdown_percent=params["max_drawdown_percent"],
        max_trades=params["max_trades"],
        sentiment_sizing_multiplier=params["sentiment_sizing_multiplier"],
        atr_period=params["atr_period"],
        atr_trend_threshold=params["atr_trend_threshold"],
        breakout_rr_ratio=params["breakout_rr_ratio"],
        grid_levels=params["grid_levels"],
        grid_step_percent=params["grid_step_percent"],
        grid_profit_target_percent=params["grid_profit_target_percent"],
        grid_invalidation_percent=params["grid_invalidation_percent"],
        risk_per_trade_percent=params["risk_per_trade_percent"],
        trade_mode="PERCENTAGE",
        fixed_trade_amount_usdt=5.0,
        sentiment_threshold_positive=params["sentiment_threshold_positive"],
        sentiment_threshold_negative=params["sentiment_threshold_negative"],
        base_rsi_oversold=params["base_rsi_oversold"],
        base_rsi_overbought=params["base_rsi_overbought"],
        use_bollinger_bands=params["use_bollinger_bands"],
        bb_window=params.get("bb_window", 20),       # only suggested when BB enabled
        bb_window_dev=params.get("bb_window_dev", 2.0),
        sentiment_csv_file=sentiment_csv,
        symbol=symbol,
    )


def effective_params(params):
    """strategy_backtest uses `x or default`, so tuned 0.0 thresholds silently
    become the config defaults. Export the values that were ACTUALLY used."""
    out = dict(params)
    out.setdefault("bb_window", 20)      # Optuna only suggests these when BB is on
    out.setdefault("bb_window_dev", 2.0)
    if out["sentiment_threshold_positive"] == 0.0:
        out["sentiment_threshold_positive"] = 0.1  # config default
    if out["sentiment_threshold_negative"] == 0.0:
        out["sentiment_threshold_negative"] = -0.1  # config default
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=25)
    ap.add_argument("--candles", type=int, default=None, help="use only the last N candles per symbol (faster first pass)")
    ap.add_argument("--start", default=None, help="inclusive UTC timestamp lower bound (shared window)")
    ap.add_argument("--end", default=None, help="inclusive UTC timestamp upper bound")
    ap.add_argument("--symbols", nargs="*", default=SYMBOLS)
    ap.add_argument("--out", default=os.path.join(ROOT, "cloudflare", "src", "tuned_params.json"))
    args = ap.parse_args()

    sentiment_csv = os.path.join(ROOT, "data_acquisition", "historical_sentiment.csv")
    client = Client("", "")  # public endpoints only
    result = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trials_per_symbol": args.trials,
        "source": "backtest/optimize_params.py search space + backtest/strategy_backtest",
        "data": "1h CSVs from backtest/, historical_sentiment.csv",
        "symbols": {},
    }

    for symbol in args.symbols:
        csv_path = os.path.join(HERE, f"{symbol}_1h.csv")
        df = load_data(csv_path)
        if args.candles:
            df = df.iloc[-args.candles:]
        if args.start:
            df = df[df.timestamp >= args.start]
        if args.end:
            df = df[df.timestamp <= args.end]
        print(f"[tune] {symbol}: {len(df)} candles {df.timestamp.min()} -> {df.timestamp.max()}", flush=True)
        study = optuna.create_study(direction="maximize")
        def progress(study, trial):
            if trial.number % 2 == 0:
                print(f"[trial] {symbol} #{trial.number} best=${study.best_value:.2f}", flush=True)
        study.optimize(lambda t: objective(t, df, client, symbol, sentiment_csv), n_trials=args.trials, callbacks=[progress])
        best = effective_params(study.best_params)
        trades_df, final_balance, metrics = run_backtest(df, client, symbol, sentiment_csv, best)
        entry = {
            "params": best,
            "final_balance": float(final_balance),
            "trades": int(len(trades_df)),
            "metrics": {
                k: (float(v) if isinstance(v, (int, float)) and math.isfinite(v) else str(v))
                for k, v in metrics.items()
            },
            "candles": int(len(df)),
            "window": [str(df.timestamp.min()), str(df.timestamp.max())],
        }
        result["symbols"][symbol] = entry
        print(f"[best] {symbol}: ${final_balance:.2f} over {len(trades_df)} trades | params={best}", flush=True)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[done] wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
