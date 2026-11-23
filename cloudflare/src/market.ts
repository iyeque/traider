// Binance PUBLIC market data — no API key required.
// data-api.binance.vision is Binance's keyless market-data mirror (verified reachable).

import type { Candle } from "./core/types";

const BASE = "https://data-api.binance.vision/api/v3";

export async function fetchKlines(symbol: string, interval: string, limit = 100): Promise<Candle[]> {
  const url = `${BASE}/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(10000), cf: { cacheTtl: 30, cacheEverything: true } } as RequestInit);
  if (!res.ok) throw new Error(`klines ${symbol} ${interval}: HTTP ${res.status}`);
  const rows = (await res.json()) as (string | number)[][];
  return rows.map((r) => ({
    t: Number(r[0]), o: Number(r[1]), h: Number(r[2]), l: Number(r[3]), c: Number(r[4]), v: Number(r[5]),
  }));
}

export async function fetchPrice(symbol: string): Promise<number> {
  const res = await fetch(`${BASE}/ticker/price?symbol=${symbol}`, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`ticker ${symbol}: HTTP ${res.status}`);
  const j = (await res.json()) as { price: string };
  return Number(j.price);
}
