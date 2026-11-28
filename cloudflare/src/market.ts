// Market data with provider fallbacks. Binance's keyless public mirror works
// from a normal network (WSL) but returns HTTP 403 from Cloudflare Workers
// egress (datacenter IP range), so demo accounts fall back to Coinbase
// Exchange and Kraken public OHLC endpoints — both keyless and cloud-friendly.
// Every provider is public market data; no API keys, no signed requests.

import type { Candle } from "./core/types";

const BINANCE_BASE = "https://data-api.binance.vision/api/v3";
const COINBASE_BASE = "https://api.exchange.coinbase.com/products";
const KRAKEN_BASE = "https://api.kraken.com/0/public/OHLC";
const UA = { "User-Agent": "traider-cloudflare-demo/0.1" };

const COINBASE_SYMBOL: Record<string, string> = {
  BTCUSDT: "BTC-USD", ETHUSDT: "ETH-USD", SOLUSDT: "SOL-USD", BNBUSDT: "BNB-USD",
};
const KRAKEN_SYMBOL: Record<string, string> = {
  BTCUSDT: "XBTUSD", ETHUSDT: "XETHZUSD", SOLUSDT: "SOLUSD", BNBUSDT: "BNBUSD",
};
const GRANULARITY: Record<string, number> = {
  "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
  "1h": 3600, "2h": 7200, "6h": 21600, "1d": 86400,
};
const KRAKEN_INTERVAL: Record<string, number> = {
  "1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "6h": 360, "1d": 1440,
};

// Coinbase: [time, low, high, open, close, volume]. Time is epoch SECONDS on
// the candles endpoint today (older docs show ISO strings) — handle both.
export function coinbaseCandles(rows: (string | number)[][]): Candle[] {
  return rows.map((r) => ({
    t: typeof r[0] === "number" ? r[0] * 1000 : Date.parse(String(r[0])),
    o: Number(r[3]), h: Number(r[2]), l: Number(r[1]), c: Number(r[4]), v: Number(r[5]),
  })).filter((k) => Number.isFinite(k.t) && Number.isFinite(k.c)).sort((a, b) => a.t - b.t);
}

// Kraken: { error: [], result: { PAIR: { candles: [[epochSec, o, h, l, c, vwap, vol, count], ...] } } }
export function krakenCandles(payload: any, pair: string): Candle[] {
  // Kraken canonicalizes the requested pair (XBTUSD -> XXBTZUSD), so never
  // hard-code the result key — find the entry that actually has candles.
  const entry = payload?.result?.[pair] ??
    Object.values(payload?.result ?? {}).find((v: any) => v && Array.isArray(v.candles));
  const candles = (entry as any)?.candles;
  if (!Array.isArray(candles)) return [];
  return candles.map((r: any[]) => ({
    t: Number(r[0]) * 1000,
    o: Number(r[1]), h: Number(r[2]), l: Number(r[3]), c: Number(r[4]), v: Number(r[6]),
  })).filter((k) => Number.isFinite(k.t) && Number.isFinite(k.c)).sort((a, b) => a.t - b.t);
}

async function fetchBinance(symbol: string, interval: string, limit: number): Promise<Candle[]> {
  const res = await fetch(`${BINANCE_BASE}/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`, {
    signal: AbortSignal.timeout(10000),
    cf: { cacheTtl: 30, cacheEverything: true },
  } as RequestInit);
  if (!res.ok) throw new Error(`binance ${symbol} ${interval}: HTTP ${res.status}`);
  const rows = (await res.json()) as (string | number)[][];
  return rows.map((r) => ({
    t: Number(r[0]), o: Number(r[1]), h: Number(r[2]), l: Number(r[3]), c: Number(r[4]), v: Number(r[5]),
  }));
}

async function fetchCoinbase(symbol: string, interval: string, limit: number): Promise<Candle[]> {
  const product = COINBASE_SYMBOL[symbol];
  const gran = GRANULARITY[interval];
  if (!product || !gran) throw new Error(`no Coinbase mapping for ${symbol} ${interval}`);
  const res = await fetch(`${COINBASE_BASE}/${product}/candles?granularity=${gran}`, {
    signal: AbortSignal.timeout(10000), headers: UA,
  });
  if (!res.ok) throw new Error(`coinbase ${product}: HTTP ${res.status}`);
  const rows = (await res.json()) as (string | number)[][];
  return coinbaseCandles(rows).slice(-limit);
}

async function fetchKraken(symbol: string, interval: string, limit: number): Promise<Candle[]> {
  const pair = KRAKEN_SYMBOL[symbol];
  const iv = KRAKEN_INTERVAL[interval];
  if (!pair || !iv) throw new Error(`no Kraken mapping for ${symbol} ${interval}`);
  const res = await fetch(`${KRAKEN_BASE}?pair=${pair}&interval=${iv}`, {
    signal: AbortSignal.timeout(10000), headers: UA,
  });
  if (!res.ok) throw new Error(`kraken ${pair}: HTTP ${res.status}`);
  return krakenCandles(await res.json(), pair).slice(-limit);
}

export async function fetchKlines(symbol: string, interval: string, limit = 100): Promise<Candle[]> {
  const errors: string[] = [];
  for (const provider of [fetchBinance, fetchCoinbase, fetchKraken]) {
    try {
      const candles = await provider(symbol, interval, limit);
      if (candles.length >= 30) return candles;
      errors.push(`${provider.name}: only ${candles.length} candles`);
    } catch (e) {
      errors.push(`${provider.name}: ${e instanceof Error ? e.message : String(e)}`);
    }
  }
  throw new Error(`klines ${symbol} ${interval} unavailable (${errors.join(" | ")})`);
}

export async function fetchPrice(symbol: string): Promise<number> {
  const candles = await fetchKlines(symbol, "1m", 2);
  return candles[candles.length - 1].c;
}
