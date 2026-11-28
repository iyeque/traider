#!/usr/bin/env python3
"""Per-symbol Optuna tuning with train/out-of-sample split and promotion guardrails.

Uses the EXACT 18-parameter search space from backtest/optimize_params.py and
the real backtest/strategy_backtest() on the checked-in hourly CSVs plus
historical_sentiment.csv. Optuna sees ONLY the training slice; the held-out
tail is used once to decide whether params are eligible for promotion.

No network calls: an OfflineClient supplies static exchange filters, so this
script is safe to run on GitHub-hosted runners (whose shared IPs can be
WAF-blocked by Binance).

    python3 backtest/run_per_symbol.py --symbols BTCUSDT --trials 50 \
        --test-fraction 0.25 --out tune_BTCUSDT.json
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

from backtest import load_data, strategy_backtest

optuna.logging.set_verbosity(optuna.logging.WARNING)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
STARTING_BALANCE = 10000.0


class OfflineClient:
    """Static exchangeInfo surrogate — no HTTP, deterministic on any runner."""

    def get_exchange_info(self):
        return {"symbols": [{
            "symbol": s,
            "filters": [
                {"filterType": "NOTIONAL", "minNotional": "5"},
                {"filterType": "LOT_SIZE", "stepSize": "0.000001", "minQty": "0.000001"},
            ],
        } for s in SYMBOLS]}


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
    return final_balance  # train objective only


def run_backtest(df, client, symbol, sentiment_csv, params):
    return strategy_backtest(
        client, df, starting_balance=STARTING_BALANCE,
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
        bb_window=params.get("bb_window", 20),
        bb_window_dev=params.get("bb_window_dev", 2.0),
        sentiment_csv_file=sentiment_csv,
        symbol=symbol,
    )


def effective_params(params):
    """strategy_backtest uses `x or default`, so tuned 0.0 thresholds silently
    become config defaults. Export the values that were ACTUALLY used."""
    out = dict(params)
    out.setdefault("bb_window", 20)
    out.setdefault("bb_window_dev", 2.0)
    if out["sentiment_threshold_positive"] == 0.0:
        out["sentiment_threshold_positive"] = 0.1
    if out["sentiment_threshold_negative"] == 0.0:
        out["sentiment_threshold_negative"] = -0.1
    return out


def clean_metrics(metrics):
    return {
        k: (float(v) if isinstance(v, (int, float)) and math.isfinite(v) else str(v))
        for k, v in metrics.items()
    }


def promotion_check(eval_entry):
    """Guardrails on the OUT-OF-SAMPLE slice (max_drawdown is already a %)."""
    m = eval_entry["metrics"]
    reasons = []
    oos_return = (eval_entry["final_balance"] - STARTING_BALANCE) / STARTING_BALANCE * 100
    if oos_return <= 0:
        reasons.append(f"out-of-sample return {oos_return:.2f}% <= 0")
    if eval_entry["trades"] < 3:
        reasons.append(f"only {eval_entry['trades']} out-of-sample trades (<3)")
    pf = m.get("profit_factor", 0)
    pf_value = math.inf if str(pf) in ("inf", "Infinity") else float(pf)
    if pf_value <= 1.2:
        reasons.append(f"profit factor {pf} <= 1.2")
    wr = float(m.get("win_rate", 0))
    if wr < 0.45:
        reasons.append(f"win rate {wr:.2f} < 0.45")
    dd = float(m.get("max_drawdown", 100))
    if dd >= 20:
        reasons.append(f"max drawdown {dd:.1f}% >= 20%")
    return {"eligible": not reasons, "reasons": reasons, "oos_return_pct": oos_return}


def evaluate(df, client, symbol, sentiment_csv, params):
    trades, balance, metrics = run_backtest(df, client, symbol, sentiment_csv, params)
    return {
        "final_balance": float(balance),
        "trades": int(len(trades)),
        "metrics": clean_metrics(metrics),
        "window": [str(df.timestamp.min()), str(df.timestamp.max())],
        "candles": int(len(df)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=25)
    ap.add_argument("--candles", type=int, default=None, help="use only the last N candles per symbol")
    ap.add_argument("--start", default=None, help="inclusive UTC timestamp lower bound")
    ap.add_argument("--end", default=None, help="inclusive UTC timestamp upper bound")
    ap.add_argument("--test-fraction", type=float, default=0.0,
                    help="hold out the last fraction for out-of-sample validation (0 = no split)")
    ap.add_argument("--symbols", nargs="*", default=SYMBOLS)
    ap.add_argument("--out", default="tune_result.json")
    args = ap.parse_args()

    sentiment_csv = os.path.join(ROOT, "data_acquisition", "historical_sentiment.csv")
    client = OfflineClient()  # no HTTP: safe on shared runner IPs
    result = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trials_per_symbol": args.trials,
        "test_fraction": args.test_fraction,
        "source": "backtest/optimize_params.py search space + backtest/strategy_backtest",
        "data": "checked-in 1h CSVs + historical_sentiment.csv (no network)",
        "symbols": {},
    }

    for symbol in args.symbols:
        df = load_data(os.path.join(HERE, f"{symbol}_1h.csv"))
        if args.candles:
            df = df.iloc[-args.candles:]
        if args.start:
            df = df[df.timestamp >= args.start]
        if args.end:
            df = df[df.timestamp <= args.end]
        split = int(len(df) * (1 - args.test_fraction)) if args.test_fraction > 0 else len(df)
        train_df, test_df = df.iloc[:split], df.iloc[split:]
        if len(train_df) < 30 or (args.test_fraction > 0 and len(test_df) < 30):
            raise RuntimeError(f"{symbol}: insufficient candles for split ({len(train_df)}/{len(test_df)})")
        print(f"[tune] {symbol}: train={len(train_df)} test={len(test_df)} "
              f"({train_df.timestamp.min()} -> {df.timestamp.max()})", flush=True)

        study = optuna.create_study(direction="maximize")
        def progress(s, t):
            if t.number % 10 == 0:
                print(f"[trial] {symbol} #{t.number} best=${s.best_value:.2f}", flush=True)
        study.optimize(lambda t: objective(t, train_df, client, symbol, sentiment_csv),
                       n_trials=args.trials, callbacks=[progress])
        best = effective_params(study.best_params)
        train_eval = evaluate(train_df, client, symbol, sentiment_csv, best)
        oos_eval = evaluate(test_df, client, symbol, sentiment_csv, best) if len(test_df) else None
        promotion = promotion_check(oos_eval) if oos_eval else None
        entry = {
            "params": best,
            "train": train_eval,
            "oos": oos_eval,
            "promotion": promotion,
            # backward-compatible top-level fields
            "final_balance": (oos_eval or train_eval)["final_balance"],
            "trades": (oos_eval or train_eval)["trades"],
            "metrics": (oos_eval or train_eval)["metrics"],
            "candles": int(len(df)),
            "window": [str(df.timestamp.min()), str(df.timestamp.max())],
        }
        result["symbols"][symbol] = entry
        verdict = "n/a" if not promotion else ("PROMOTE" if promotion["eligible"] else "NO: " + "; ".join(promotion["reasons"]))
        if oos_eval is not None:
            oos_str = f"${oos_eval['final_balance']:.2f}"
        else:
            oos_str = "n/a"
        print(f"[best] {symbol}: train=${train_eval['final_balance']:.2f} oos={oos_str} | {verdict}", flush=True)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[done] wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
