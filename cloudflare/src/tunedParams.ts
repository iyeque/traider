// Maps Optuna's snake_case output (backtest/run_per_symbol.py) onto the TS
// StrategyConfig keys. Parameters absent from the JSON keep DEFAULT_CONFIG.

import tuned from "./tuned_params.json";
import type { StrategyConfig } from "./core/types";

type RawParams = Record<string, number | boolean | string>;
const TABLE = tuned as unknown as {
  symbols: Record<string, { params: RawParams } | undefined>;
};

export function tunedConfigFor(symbol: string): Partial<StrategyConfig> {
  const entry = TABLE.symbols[symbol];
  if (!entry) return {};
  const p = entry.params;
  const out: Partial<StrategyConfig> = {};
  const num = (key: keyof StrategyConfig, raw: string) => {
    const v = p[raw];
    if (typeof v === "number") (out as Record<string, unknown>)[key] = v;
  };
  num("atrPeriod", "atr_period");
  num("atrTrendThreshold", "atr_trend_threshold");
  num("breakoutRrRatio", "breakout_rr_ratio");
  num("gridLevels", "grid_levels");
  num("gridStepPercent", "grid_step_percent");
  num("gridProfitTargetPercent", "grid_profit_target_percent");
  num("gridInvalidationPercent", "grid_invalidation_percent");
  num("riskPerTradePercent", "risk_per_trade_percent");
  num("sentimentThresholdPositive", "sentiment_threshold_positive");
  num("sentimentThresholdNegative", "sentiment_threshold_negative");
  num("volumeFactor", "volume_factor");
  num("sentimentSizingMultiplier", "sentiment_sizing_multiplier");
  num("baseRsiOversold", "base_rsi_oversold");
  num("baseRsiOverbought", "base_rsi_overbought");
  num("bbWindow", "bb_window");
  num("bbWindowDev", "bb_window_dev");
  if (typeof p.use_bollinger_bands === "boolean") out.useBollingerBands = p.use_bollinger_bands;
  return out;
}
