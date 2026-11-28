import { describe, it, expect } from "vitest";
import fixture from "./fixtures/python_fidelity.json";
import { generateSignal, selectStrategy, calculateTradeSize, breakoutLevels, gridLadder, isMarketSafe } from "../src/core/strategy";

describe("Python fidelity: generate_signal (108 cases from the real function)", () => {
  for (const [idx, c] of (fixture.signalCases as any[]).entries()) {
    it(`case ${idx}: rsi=${c.rsi} macd=${c.macd}/${c.macdSignal} sent=${c.sentiment}${c.useBB ? " BB" : ""} -> ${c.expected}`, () => {
      const out = generateSignal({
        rsi: c.rsi, macd: c.macd, macdSignal: c.macdSignal, sentiment: c.sentiment,
        sentimentThresholdPositive: 0.0, sentimentThresholdNegative: -0.1,
        baseRsiOversold: 30, baseRsiOverbought: 70,
        useBollingerBands: !!c.useBB, bbLower: c.bbLower ?? null, bbUpper: c.bbUpper ?? null,
        currentClose: c.close ?? 50000,
      });
      expect(out).toBe(c.expected);
    });
  }
});

describe("Python fidelity: calculate_trade_size", () => {
  for (const [idx, c] of (fixture.tradeSizeCases as any[]).entries()) {
    it(`case ${idx} (${c.mode} bal=${c.balance} sent=${c.sentiment})`, () => {
      const out = calculateTradeSize(c.balance, c.mode, c.risk, c.sentiment, c.fixed, c.mult);
      expect(out).toBeCloseTo(c.expected, 9);
    });
  }
});

describe("regime selection (main.py)", () => {
  it("ATR/price above threshold -> breakout (trending)", () => {
    expect(selectStrategy(300, 10000, 0.02)).toBe("breakout");
  });
  it("below threshold -> grid (sideways)", () => {
    expect(selectStrategy(100, 10000, 0.02)).toBe("grid");
  });
  it("exactly at threshold -> grid (strict >)", () => {
    expect(selectStrategy(200, 10000, 0.02)).toBe("grid");
  });
});

describe("breakout SL/TP (bot/trading.py formulas)", () => {
  it("buy: sl = price - 2*atr, tp = price + rr*(price-sl), qty = amount/(price-sl)", () => {
    const { sl, tp, qty } = breakoutLevels(50000, 100, 2.5, "buy", 100);
    expect(sl).toBe(49800); expect(tp).toBe(50500); expect(qty).toBe(0.5);
  });
  it("sell: sl = price + 2*atr, tp = price - rr*(sl-price)", () => {
    const { sl, tp, qty } = breakoutLevels(50000, 100, 2.5, "sell", 100);
    expect(sl).toBe(50200); expect(tp).toBe(49500); expect(qty).toBe(0.5);
  });
});

describe("grid ladder (bot/grid.py formulas)", () => {
  it("builds levels, TPs and invalidation exactly", () => {
    const g = gridLadder(50000, 300, 3, 1.0, 1.5, 2.0, 5);
    expect(g.ok).toBe(true);
    expect(g.levels.map((l) => l.buyPrice)).toEqual([49500, 49000, 48500]);
    expect(g.levels[0].qty).toBeCloseTo(100 / 49500, 12);
    expect(g.levels[0].tpPrice).toBeCloseTo(49500 * 1.015, 9);
    expect(g.invalidationPrice).toBeCloseTo(48500 * 0.98, 9);
  });
  it("rejects base quantity below minNotional*levels", () => {
    const g = gridLadder(50000, 10, 3, 1.0, 1.5, 2.0, 5);
    expect(g.ok).toBe(false);
  });
});

describe("safety gate (bot/sentiment_engine.py, quirk preserved)", () => {
  it("bearish sentiment blocks", () => {
    expect(isMarketSafe(-0.2, 50, 0.0, 30).safe).toBe(false);
  });
  it("low Fear & Greed still allows (Python return False is commented out)", () => {
    const r = isMarketSafe(0.1, 10, 0.0, 30);
    expect(r.safe).toBe(true);
    expect(r.reason).toMatch(/quirk/);
  });
  it("null Fear & Greed still allows", () => {
    expect(isMarketSafe(0.1, null, 0.0, 30).safe).toBe(true);
  });
  it("healthy readings allow", () => {
    expect(isMarketSafe(0.1, 50, 0.0, 30).safe).toBe(true);
  });
});
