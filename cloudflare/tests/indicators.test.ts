import { describe, it, expect } from "vitest";
import fixture from "./fixtures/python_fidelity.json";
import { rsi, macd, atr, bollinger, applyIndicators } from "../src/core/indicators";

// Fidelity gate: every array below was produced by the REAL Python bot
// (bot/strategy.py with pandas + ta) on the same 120 synthetic candles.
const candles = fixture.candles as { timestamp: number; open: number; high: number; low: number; close: number; volume: number }[];
const closes = candles.map((k) => k.close);
const highs = candles.map((k) => k.high);
const lows = candles.map((k) => k.low);

function expectClose(actual: number[], expected: (number | null)[], tol = 1e-9) {
  expect(actual.length).toBe(expected.length);
  for (let i = 0; i < expected.length; i++) {
    const e = expected[i];
    if (e === null) {
      expect(Number.isNaN(actual[i]), `index ${i} should be NaN`).toBe(true);
    } else {
      expect(Math.abs(actual[i] - e), `index ${i}: ${actual[i]} vs ${e}`).toBeLessThanOrEqual(tol * Math.max(1, Math.abs(e)));
    }
  }
}

describe("Python fidelity: indicators", () => {
  it("RSI matches pandas rolling-mean implementation", () => {
    expectClose(rsi(closes, 14), fixture.rsi as (number | null)[]);
  });
  it("MACD line + signal match ewm(adjust=False)", () => {
    const m = macd(closes);
    expectClose(m.macd, fixture.macd as (number | null)[]);
    expectClose(m.signal, fixture.macdSignal as (number | null)[]);
  });
  it("ATR(14) matches rolling mean of true range", () => {
    expectClose(atr(highs, lows, closes, 14), fixture.atr14 as (number | null)[]);
  });
  it("Bollinger(20, 2.0) matches ta (sample std, ddof=1)", () => {
    const bb = bollinger(closes, 20, 2.0);
    const exp = (fixture.bb as any).dev2;
    expectClose(bb.mid, exp.mid); expectClose(bb.upper, exp.upper); expectClose(bb.lower, exp.lower);
  });
  it("Bollinger dev=1.5 is cast to int 1 (Python quirk preserved)", () => {
    const bb = bollinger(closes, 20, 1.5);
    const exp = (fixture.bb as any).dev15;
    expectClose(bb.mid, exp.mid); expectClose(bb.upper, exp.upper); expectClose(bb.lower, exp.lower);
  });
  it("applyIndicators composes the same values", () => {
    const set = applyIndicators(candles.map((k) => ({ h: k.high, l: k.low, c: k.close })), 14, true, 20, 2.0);
    expectClose(set.rsi, fixture.rsi as (number | null)[]);
    expectClose(set.atr, fixture.atr14 as (number | null)[]);
    expectClose(set.bbLower!, (fixture.bb as any).dev2.lower);
  });
});
