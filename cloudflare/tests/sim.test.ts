import { describe, it, expect } from "vitest";
import { realizedPnl, marketFill, slippagePct, checkExit, gridBuyFilled, drawdownPct, unrealizedPnl } from "../src/core/sim";
import { DEFAULT_CONFIG } from "../src/core/types";
import type { Position, Candle } from "../src/core/types";

const cfg = { ...DEFAULT_CONFIG };
const candle = (l: number, h: number): Candle => ({ t: 0, o: (l + h) / 2, h, l, c: (l + h) / 2, v: 1 });
const pos = (p: Partial<Position>): Position => ({
  id: "p1", symbol: "BTCUSDT", side: "buy", strategy: "breakout",
  entryPrice: 100, qty: 2, sl: 90, tp: 110, invalidation: null, openedAt: 0, ...p,
});

describe("PnL (bot/position_manager.py exact)", () => {
  it("long: (exit-entry)*qty", () => expect(realizedPnl(100, 110, 2, "buy")).toBe(20));
  it("short sign flipped", () => expect(realizedPnl(100, 110, 2, "sell")).toBe(-20));
  it("long loss", () => expect(realizedPnl(100, 90, 2, "buy")).toBe(-20));
  it("unrealized uses same formula", () => expect(unrealizedPnl(pos({}), 105)).toBe(10));
});

describe("demo fill model", () => {
  it("slippage grows with quantity", () => {
    expect(slippagePct(10, cfg)).toBeCloseTo(0.0005 + 10 * 1e-6, 12);
    expect(slippagePct(1000, cfg)).toBeGreaterThan(slippagePct(10, cfg));
  });
  it("buy fills above mark, sell below; fee on notional", () => {
    const b = marketFill(100, "buy", 10, cfg);
    expect(b.fillPrice).toBeCloseTo(100 * 1.00051, 9);
    expect(b.fee).toBeCloseTo(b.fillPrice * 10 * 0.001, 9);
    const s = marketFill(100, "sell", 10, cfg);
    expect(s.fillPrice).toBeCloseTo(100 * 0.99949, 9);
  });
});

describe("exit checks", () => {
  it("breakout buy: stop assumed first when both SL and TP in range", () => {
    const ex = checkExit(pos({}), candle(85, 115));
    expect(ex).toEqual({ hit: true, exitPrice: 90, kind: "sl" });
  });
  it("breakout buy: TP hit", () => {
    expect(checkExit(pos({}), candle(95, 112))).toEqual({ hit: true, exitPrice: 110, kind: "tp" });
  });
  it("breakout buy: no hit", () => {
    expect(checkExit(pos({}), candle(95, 105)).hit).toBe(false);
  });
  it("breakout sell: mirrored (stop above, tp below)", () => {
    const p = pos({ side: "sell", sl: 110, tp: 90 });
    expect(checkExit(p, candle(85, 115)).kind).toBe("sl");
    expect(checkExit(p, candle(88, 105)).kind).toBe("tp");
  });
  it("grid: invalidation before TP", () => {
    const p = pos({ strategy: "grid", sl: null, tp: 110, invalidation: 80 });
    expect(checkExit(p, candle(75, 115))).toEqual({ hit: true, exitPrice: 80, kind: "invalidation" });
    expect(checkExit(p, candle(85, 112)).kind).toBe("tp");
  });
  it("grid limit buy fills when low trades through the level", () => {
    expect(gridBuyFilled({ buyPrice: 95 }, candle(94, 100))).toBe(true);
    expect(gridBuyFilled({ buyPrice: 95 }, candle(96, 100))).toBe(false);
  });
});

describe("drawdown guard", () => {
  it("25% drawdown computed from peak", () => expect(drawdownPct(1000, 750)).toBe(25));
  it("no drawdown at new peak", () => expect(drawdownPct(1000, 1100)).toBe(0));
});
