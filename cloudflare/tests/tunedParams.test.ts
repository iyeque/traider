import { describe, it, expect } from "vitest";
import tuned from "../src/tuned_params.json";
import { tunedConfigFor } from "../src/tunedParams";
import { DEFAULT_CONFIG } from "../src/core/types";

describe("per-token tuned params from the real Python backtest", () => {
  for (const symbol of ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]) {
    it(`${symbol} maps Optuna output onto StrategyConfig`, () => {
      const raw = (tuned as any).symbols[symbol];
      expect(raw).toBeDefined();
      const cfg = { ...DEFAULT_CONFIG, ...tunedConfigFor(symbol) };
      expect(cfg.atrPeriod).toBe(raw.params.atr_period);
      expect(cfg.gridLevels).toBe(raw.params.grid_levels);
      expect(cfg.riskPerTradePercent).toBe(raw.params.risk_per_trade_percent);
      expect(cfg.sentimentThresholdPositive).toBe(raw.params.sentiment_threshold_positive);
      expect(cfg.useBollingerBands).toBe(raw.params.use_bollinger_bands);
      expect(Number.isFinite(cfg.volumeFactor)).toBe(true);
    });
  }
  it("unknown symbol leaves defaults intact", () => {
    expect(tunedConfigFor("DOGEUSDT")).toEqual({});
  });
});
