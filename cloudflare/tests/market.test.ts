import { describe, it, expect } from "vitest";
import { coinbaseCandles, krakenCandles } from "../src/market";

describe("public-data provider adapters (no keys)", () => {
  it("Coinbase [time,low,high,open,close,volume] -> Candle, time-sorted", () => {
    const rows = [
      ["2026-11-23T10:00:00Z", 100, 110, 105, 108, 12],
      ["2026-11-23T09:00:00Z", 95, 105, 100, 102, 9],
    ];
    const out = coinbaseCandles(rows as any);
    expect(out.length).toBe(2);
    expect(out[0].t).toBe(Date.parse("2026-11-23T09:00:00Z"));
    expect(out[0].o).toBe(100); expect(out[0].h).toBe(105);
    expect(out[0].l).toBe(95); expect(out[0].c).toBe(102); expect(out[0].v).toBe(9);
  });

  it("Coinbase numeric epoch time (current API shape)", () => {
    const out = coinbaseCandles([[1795451400, 100, 110, 105, 108, 12]] as any);
    expect(out[0].t).toBe(1795451400000);
    expect(out[0].l).toBe(100); expect(out[0].h).toBe(110); expect(out[0].c).toBe(108);
  });

  it("Kraken canonical pair key (XXBTZUSD) found automatically", () => {
    const payload = { error: [], result: { XXBTZUSD: { candles: [[1700000000, "100", "110", "95", "105", "103", "7", 3]] }, last: "x" } };
    const out = krakenCandles(payload, "XBTUSD");
    expect(out.length).toBe(1); expect(out[0].t).toBe(1700000000000);
  });

  it("Kraken candles array -> Candle, epoch seconds -> ms", () => {
    const payload = { error: [], result: { XBTUSD: { candles: [
      [1700000000, "100", "110", "95", "105", "103", "12.5", 42],
      [1700003600, "105", "115", "100", "112", "108", "9.1", 30],
    ] } } };
    const out = krakenCandles(payload, "XBTUSD");
    expect(out.length).toBe(2);
    expect(out[0].t).toBe(1700000000000);
    expect(out[0].o).toBe(100); expect(out[0].h).toBe(110); expect(out[0].l).toBe(95);
    expect(out[0].c).toBe(105); expect(out[0].v).toBe(12.5);
  });

  it("malformed Kraken payload -> empty (provider fallback proceeds)", () => {
    expect(krakenCandles({ error: ["E"] }, "XBTUSD")).toEqual([]);
  });
});
