// Faithful port of the decision logic:
//  - bot/strategy.py generate_signal
//  - bot/trading.py calculate_trade_size + SL/TP construction
//  - bot/grid.py place_grid_orders ladder math
//  - main.py regime selection (ATR/price vs threshold)

import type { Candle, Signal, Side, StrategyConfig, StrategyName } from "./types";

export function generateSignal(p: {
  rsi: number; macd: number; macdSignal: number; sentiment: number;
  sentimentThresholdPositive: number; sentimentThresholdNegative: number;
  baseRsiOversold: number; baseRsiOverbought: number;
  useBollingerBands: boolean; bbLower: number | null; bbUpper: number | null;
  currentClose: number;
}): Signal {
  // Sentiment-adjusted RSI thresholds (exact Python formula)
  const adjOversold = p.baseRsiOversold - p.sentiment * 10;
  const adjOverbought = p.baseRsiOverbought - p.sentiment * 10;

  const macdBull = p.macd > p.macdSignal;
  const rsiOversold = p.rsi < adjOversold;
  const sentPos = p.sentiment > p.sentimentThresholdPositive;
  let bbBuy = true;
  if (p.useBollingerBands && p.bbLower !== null) bbBuy = p.currentClose < p.bbLower;
  if (macdBull && rsiOversold && sentPos && bbBuy) return "buy";

  const macdBear = p.macd < p.macdSignal;
  const rsiOverbought = p.rsi > adjOverbought;
  const sentNeg = p.sentiment < p.sentimentThresholdNegative;
  let bbSell = true;
  if (p.useBollingerBands && p.bbUpper !== null) bbSell = p.currentClose > p.bbUpper;
  if (macdBear && rsiOverbought && sentNeg && bbSell) return "sell";

  return null;
}

// main.py: 'trending' if atr/price > ATR_TREND_THRESHOLD else 'sideways'
// scheduler: trending -> breakout, sideways -> grid
export function selectStrategy(atrLast: number, price: number, threshold: number): StrategyName {
  return atrLast / price > threshold ? "breakout" : "grid";
}

// bot/trading.py calculate_trade_size — exact port
export function calculateTradeSize(
  balance: number, tradeMode: string, riskPerTradePercent: number,
  currentSentiment: number, fixedTradeAmountUsdt = 5.0, sentimentSizingMultiplier = 0.0,
): number {
  let baseAmount: number;
  if (tradeMode === "FIXED") baseAmount = fixedTradeAmountUsdt;
  else baseAmount = Math.max(balance * (riskPerTradePercent / 100), fixedTradeAmountUsdt);
  const adjusted = baseAmount * (1 + currentSentiment * sentimentSizingMultiplier);
  return Math.max(adjusted, fixedTradeAmountUsdt);
}

// bot/trading.py place_market_order_with_sl_tp — SL/TP from 1m ATR
export function breakoutLevels(price: number, atr1m: number, rrRatio: number, side: Side, amountToRisk: number) {
  let sl: number, tp: number;
  if (side === "buy") {
    sl = price - 2 * atr1m;
    tp = price + rrRatio * (price - sl);
  } else {
    sl = price + 2 * atr1m;
    tp = price - rrRatio * (sl - price);
  }
  const qty = amountToRisk / Math.abs(price - sl);
  return { sl, tp, qty };
}

export interface GridLevel { buyPrice: number; qty: number; tpPrice: number; }

// bot/grid.py place_grid_orders — ladder math (order placement simulated in demo)
export function gridLadder(
  currentPrice: number, baseQty: number, levels: number, stepPct: number,
  profitTargetPct: number, invalidationPct: number, minNotional: number,
): { ok: boolean; reason?: string; levels: GridLevel[]; invalidationPrice: number } {
  if (baseQty < minNotional * levels) {
    return { ok: false, reason: `base quantity ${baseQty} too low for ${levels} levels at min notional ${minNotional}`, levels: [], invalidationPrice: 0 };
  }
  const amountPerLevel = baseQty / levels;
  const lastBuyPrice = currentPrice * (1 - (levels * stepPct) / 100);
  const invalidationPrice = lastBuyPrice * (1 - invalidationPct / 100);
  const out: GridLevel[] = [];
  for (let i = 1; i <= levels; i++) {
    const buyPrice = currentPrice * (1 - (i * stepPct) / 100);
    const qty = amountPerLevel / buyPrice;
    if (qty * buyPrice < minNotional) continue; // Python logs + skips sub-min-notional levels
    out.push({ buyPrice, qty, tpPrice: buyPrice * (1 + profitTargetPct / 100) });
  }
  if (out.length === 0) return { ok: false, reason: "no grid levels meet min notional", levels: [], invalidationPrice };
  return { ok: true, levels: out, invalidationPrice };
}

// bot/sentiment_engine.py is_market_safe — exact port INCLUDING the Python quirk:
// low Fear & Greed logs a warning but still returns True (the `return False` is
// commented out in the source "for testing purposes"). Preserved deliberately.
export function isMarketSafe(sentiment: number, fearGreed: number | null, minSentiment: number, minFearGreed: number):
  { safe: boolean; reason: string | null } {
  if (sentiment < minSentiment) return { safe: false, reason: `sentiment too bearish (${sentiment.toFixed(2)} < ${minSentiment.toFixed(2)})` };
  if (fearGreed === null || fearGreed < minFearGreed) {
    return { safe: true, reason: `Fear & Greed low (${fearGreed} < ${minFearGreed}) — allowed (Python quirk preserved)` };
  }
  return { safe: true, reason: null };
}
