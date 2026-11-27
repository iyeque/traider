#!/usr/bin/env python3
"""Daily data refresh for Traider tuning (Phase 1b second half).

Fetches a rolling 1000 x 1h OHLCV window for the four demo symbols from
Binance's keyless public market-data mirror (works from a home/WSL IP; it is
WAF-blocked from Cloudflare/GitHub runners), and refreshes hourly sentiment
from NewsAPI + RSS (CryptoPanic is skipped — its v1 endpoint 403s).

Writes/overwrites the CSVs the tuner consumes, then optionally commits them
to cloudflare-agents so the bi-weekly Action always reads fresh data.

    python3 backtest/refresh_data.py                 # refresh files only
    python3 backtest/refresh_data.py --commit        # refresh + push to branch
"""

import argparse
import datetime
import os
import subprocess
import sys

import logging
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from data_acquisition.fetch_historical_data import (
    fetch_newsapi_news, fetch_rss_feed, process_articles_for_sentiment,
    aggregate_hourly_sentiment,
)

# The upstream module logs request URLs (including apiKey) on HTTP errors.
# Keep that logger quiet — no secrets in cron logs.
logging.getLogger("data_acquisition.fetch_historical_data").setLevel(logging.CRITICAL)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
KLINES_URL = "https://data-api.binance.vision/api/v3/klines"
RSS_FEEDS = ["https://cointelegraph.com/rss", "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"]
DEFAULT_ENV = "/mnt/c/Users/Huawei/Downloads/Traider/.env"


def load_env(path):
    env = {}
    if not os.path.exists(path):
        return env
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.split("#")[0].strip().strip('"\'')
    return env


def fetch_ohlcv(symbol, interval="1h", limit=1000):
    r = requests.get(KLINES_URL, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=25)
    r.raise_for_status()
    rows = r.json()
    df = pd.DataFrame(rows, columns=[
        "timestamp", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
    ])
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col])
    return df


def refresh_sentiment(env, days=30):
    now = datetime.datetime.now(datetime.timezone.utc)
    start = (now - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    frames = []
    key = env.get("NEWSAPI_KEY")
    if key:
        # The upstream fetcher logs the full request URL (with apiKey) on 429.
        # Suppress ALL logging for that call so secrets never reach cron logs.
        logging.disable(logging.CRITICAL)
        try:
            articles = fetch_newsapi_news(key, from_date=start, to_date=end)
        finally:
            logging.disable(logging.NOTSET)
        print(f"[sentiment] NewsAPI articles: {len(articles)} (429 fallback to RSS if 0)", flush=True)
        frames.append(process_articles_for_sentiment(articles, "newsapi"))
    else:
        print("[sentiment] no NEWSAPI_KEY — RSS only", flush=True)
    for feed in RSS_FEEDS:
        entries = fetch_rss_feed(feed)
        print(f"[sentiment] RSS {feed[:40]}...: {len(entries)}", flush=True)
        frames.append(process_articles_for_sentiment(entries, "rss"))
    fresh = aggregate_hourly_sentiment(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame()
    path = os.path.join(ROOT, "data_acquisition", "historical_sentiment.csv")
    if os.path.exists(path):
        old = pd.read_csv(path)
        old["timestamp"] = pd.to_datetime(old["timestamp"], utc=True)
        fresh = pd.concat([old, fresh], ignore_index=True)
    fresh = fresh.drop_duplicates("timestamp").sort_values("timestamp")
    fresh.to_csv(path, index=False)
    print(f"[sentiment] wrote {len(fresh)} hourly rows -> {path}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=SYMBOLS)
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--days", type=int, default=30, help="sentiment lookback days")
    ap.add_argument("--env", default=DEFAULT_ENV)
    ap.add_argument("--commit", action="store_true", help="commit and push CSVs to cloudflare-agents")
    args = ap.parse_args()

    for symbol in args.symbols:
        df = fetch_ohlcv(symbol, "1h", args.limit)
        path = os.path.join(HERE, f"{symbol}_1h.csv")
        df.to_csv(path, index=False)
        print(f"[ohlcv] {symbol}: {len(df)} candles {df.timestamp.min()} -> {df.timestamp.max()} -> {os.path.basename(path)}", flush=True)

    refresh_sentiment(load_env(args.env), args.days)

    if args.commit:
        paths = [f"backtest/{s}_1h.csv" for s in SYMBOLS] + ["data_acquisition/historical_sentiment.csv"]
        subprocess.run(["git", "-C", ROOT, "add", "-f", *paths], check=True)
        r = subprocess.run(["git", "-C", ROOT, "diff", "--cached", "--quiet"])
        if r.returncode == 0:
            print("[git] no data changes to commit", flush=True)
        else:
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
            subprocess.run(["git", "-C", ROOT, "commit", "-q", "-m", f"data(daily): refresh tuning CSVs {stamp}"], check=True)
            subprocess.run(["git", "-C", ROOT, "push", "-q", "origin", "cloudflare-agents"], check=True)
            print("[git] pushed refreshed CSVs to cloudflare-agents", flush=True)


if __name__ == "__main__":
    main()
