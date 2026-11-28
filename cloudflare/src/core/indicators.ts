// Faithful TypeScript port of bot/strategy.py indicators.
// Semantics matched to pandas/ta exactly (verified against Python-generated fixtures):
//  - RSI: simple rolling MEAN of gains/losses (NOT Wilder's smoothing).
//    pandas delta.where(delta>0, 0) turns the first NaN delta into 0, so the
//    first valid RSI lands at index period-1 (window includes that leading 0).
//  - MACD: EMA with adjust=False (seed = first value, alpha = 2/(span+1)).
//  - ATR: simple rolling mean of True Range; TR[0] = high-low (prev close NaN).
//  - Bollinger: rolling POPULATION std (ddof=0 — matches ta, verified against fixtures); the Python
//    code casts window_dev to int inside ta.BollingerBands — quirk preserved.

export function sma(values: number[], period: number): number[] {
  const out: number[] = new Array(values.length).fill(NaN);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

function rollingStd(values: number[], period: number): number[] {
  const out: number[] = new Array(values.length).fill(NaN);
  for (let i = period - 1; i < values.length; i++) {
    let mean = 0;
    for (let j = i - period + 1; j <= i; j++) mean += values[j];
    mean /= period;
    let ss = 0;
    for (let j = i - period + 1; j <= i; j++) ss += (values[j] - mean) ** 2;
    out[i] = Math.sqrt(ss / period); // ddof=0 — ta's BollingerBands uses POPULATION std (verified vs fixture)
  }
  return out;
}

export function ema(values: number[], span: number): number[] {
  const alpha = 2 / (span + 1);
  const out: number[] = new Array(values.length).fill(NaN);
  let prev = NaN;
  for (let i = 0; i < values.length; i++) {
    const x = values[i];
    if (Number.isNaN(x)) { out[i] = prev; continue; }
    prev = Number.isNaN(prev) ? x : alpha * x + (1 - alpha) * prev;
    out[i] = prev;
  }
  return out;
}

export function rsi(closes: number[], period = 14): number[] {
  const n = closes.length;
  const gains: number[] = new Array(n).fill(0);
  const losses: number[] = new Array(n).fill(0);
  for (let i = 1; i < n; i++) {
    const d = closes[i] - closes[i - 1];
    if (d > 0) gains[i] = d;
    else if (d < 0) losses[i] = -d;
    // d === 0 or NaN -> both stay 0 (matches delta.where semantics)
  }
  const avgGain = sma(gains, period);
  const avgLoss = sma(losses, period);
  const out: number[] = new Array(n).fill(NaN);
  for (let i = 0; i < n; i++) {
    if (Number.isNaN(avgGain[i]) || Number.isNaN(avgLoss[i])) continue;
    if (avgLoss[i] === 0) { out[i] = avgGain[i] === 0 ? NaN : 100; continue; }
    const rs = avgGain[i] / avgLoss[i];
    out[i] = 100 - 100 / (1 + rs);
  }
  return out;
}

export function macd(closes: number[]): { macd: number[]; signal: number[] } {
  const e12 = ema(closes, 12);
  const e26 = ema(closes, 26);
  const line = closes.map((_, i) => e12[i] - e26[i]);
  const signal = ema(line, 9);
  return { macd: line, signal };
}

export function trueRange(h: number[], l: number[], c: number[]): number[] {
  const out: number[] = new Array(h.length).fill(NaN);
  for (let i = 0; i < h.length; i++) {
    const hl = h[i] - l[i];
    if (i === 0) { out[i] = hl; continue; }
    const hc = Math.abs(h[i] - c[i - 1]);
    const lc = Math.abs(l[i] - c[i - 1]);
    out[i] = Math.max(hl, hc, lc);
  }
  return out;
}

export function atr(h: number[], l: number[], c: number[], period = 14): number[] {
  return sma(trueRange(h, l, c), period);
}

export function bollinger(closes: number[], window = 20, windowDev = 2.0):
  { mid: number[]; upper: number[]; lower: number[] } {
  const dev = Math.trunc(windowDev); // Python: BollingerBands(window_dev=int(window_dev))
  const mid = sma(closes, window);
  const std = rollingStd(closes, window);
  const upper = mid.map((m, i) => m + dev * std[i]);
  const lower = mid.map((m, i) => m - dev * std[i]);
  return { mid, upper, lower };
}

export interface IndicatorSet {
  rsi: number[];
  macd: number[];
  macdSignal: number[];
  atr: number[];
  bbMid?: number[];
  bbUpper?: number[];
  bbLower?: number[];
}

export function applyIndicators(
  candles: { h: number; l: number; c: number }[],
  atrPeriod: number,
  useBB: boolean,
  bbWindow: number,
  bbDev: number,
): IndicatorSet {
  const closes = candles.map((k) => k.c);
  const { macd: m, signal } = macd(closes);
  const set: IndicatorSet = {
    rsi: rsi(closes, 14), // Python calculate_rsi default period=14 (fixed)
    macd: m,
    macdSignal: signal,
    atr: atr(candles.map((k) => k.h), candles.map((k) => k.l), closes, atrPeriod),
  };
  if (useBB) {
    const bb = bollinger(closes, bbWindow, bbDev);
    set.bbMid = bb.mid; set.bbUpper = bb.upper; set.bbLower = bb.lower;
  }
  return set;
}
