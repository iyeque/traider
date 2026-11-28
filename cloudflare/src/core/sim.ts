// Demo-mode trade simulation. No exchange keys, no real orders.
// Fill model uses config.py BACKTEST_* defaults: fee 0.1%, slippage =
// base(0.05%) + qty * volume_factor(1e-6). Documented in README as the demo
// fill model (the full backtest.py engine is a follow-up port).

import type { Candle, Position, Side, StrategyConfig, Trade } from "./types";

export function slippagePct(qty: number, cfg: StrategyConfig): number {
  return cfg.baseSlippagePct + qty * cfg.volumeFactor;
}

// Market fill: buy pays up through the spread, sell receives less.
export function marketFill(price: number, side: Side, qty: number, cfg: StrategyConfig):
  { fillPrice: number; fee: number } {
  const slip = slippagePct(qty, cfg);
  const fillPrice = side === "buy" ? price * (1 + slip) : price * (1 - slip);
  const fee = fillPrice * qty * cfg.feeRate;
  return { fillPrice, fee };
}

// bot/position_manager.py close_position PnL — exact port (fees tracked separately)
export function realizedPnl(entryPrice: number, exitPrice: number, qty: number, side: Side): number {
  let pnl = (exitPrice - entryPrice) * qty;
  if (side === "sell") pnl *= -1;
  return pnl;
}

export interface ExitCheck { hit: boolean; exitPrice: number; kind: "tp" | "sl" | "invalidation" | null; }

// Check a resting position against the latest candle. Conservative ordering:
// if both SL and TP are inside the candle range, the stop is assumed to hit first.
export function checkExit(pos: Position, candle: Candle): ExitCheck {
  if (pos.strategy === "grid") {
    if (pos.invalidation !== null && candle.l <= pos.invalidation) {
      return { hit: true, exitPrice: pos.invalidation, kind: "invalidation" };
    }
    if (pos.tp !== null && candle.h >= pos.tp) {
      return { hit: true, exitPrice: pos.tp, kind: "tp" };
    }
    return { hit: false, exitPrice: 0, kind: null };
  }
  // breakout (OCO): stop first if both touched
  if (pos.side === "buy") {
    if (pos.sl !== null && candle.l <= pos.sl) return { hit: true, exitPrice: pos.sl, kind: "sl" };
    if (pos.tp !== null && candle.h >= pos.tp) return { hit: true, exitPrice: pos.tp, kind: "tp" };
  } else {
    if (pos.sl !== null && candle.h >= pos.sl) return { hit: true, exitPrice: pos.sl, kind: "sl" };
    if (pos.tp !== null && candle.l <= pos.tp) return { hit: true, exitPrice: pos.tp, kind: "tp" };
  }
  return { hit: false, exitPrice: 0, kind: null };
}

// Grid limit-buy fills when price trades down through the level.
export function gridBuyFilled(level: { buyPrice: number }, candle: Candle): boolean {
  return candle.l <= level.buyPrice;
}

export function unrealizedPnl(pos: Position, markPrice: number): number {
  return realizedPnl(pos.entryPrice, markPrice, pos.qty, pos.side);
}

export function drawdownPct(peakEquity: number, equity: number): number {
  if (peakEquity <= 0) return 0;
  return Math.max(0, ((peakEquity - equity) / peakEquity) * 100);
}

let tradeSeq = 0;
export function makeTrade(partial: Omit<Trade, "id">): Trade {
  tradeSeq += 1;
  return { id: `t${Date.now().toString(36)}-${tradeSeq}`, ...partial };
}
