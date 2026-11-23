// Shared types for the Traider TypeScript port.
// Mirrors the Python bot's data shapes (bot/strategy.py, bot/trading.py, bot/grid.py).

export interface Candle {
  t: number; // open time (ms)
  o: number; // open
  h: number; // high
  l: number; // low
  c: number; // close
  v: number; // volume
}

export type Side = "buy" | "sell";
export type Signal = Side | null;
export type StrategyName = "breakout" | "grid";
export type Regime = "trending" | "sideways" | "unknown";

export interface StrategyConfig {
  interval: string;            // INTERVAL (main regime interval)
  atrPeriod: number;           // ATR_PERIOD
  atrTrendThreshold: number;   // ATR_TREND_THRESHOLD
  breakoutRrRatio: number;     // BREAKOUT_RR_RATIO
  baseRsiOversold: number;     // BASE_RSI_OVERSOLD
  baseRsiOverbought: number;   // BASE_RSI_OVERBOUGHT
  useBollingerBands: boolean;  // USE_BOLLINGER_BANDS
  bbWindow: number;            // BB_WINDOW
  bbWindowDev: number;         // BB_WINDOW_DEV (Python casts to int inside ta — preserved)
  gridLevels: number;          // GRID_LEVELS
  gridStepPercent: number;     // GRID_STEP_PERCENT
  gridProfitTargetPercent: number; // GRID_PROFIT_TARGET_PERCENT
  gridInvalidationPercent: number; // GRID_INVALIDATION_PERCENT
  sentimentThresholdPositive: number; // SENTIMENT_THRESHOLD_POSITIVE
  sentimentThresholdNegative: number; // SENTIMENT_THRESHOLD_NEGATIVE
  fearGreedThreshold: number;  // FEAR_GREED_THRESHOLD
  riskPerTradePercent: number; // RISK_PER_TRADE_PERCENT
  tradeMode: "PERCENTAGE" | "FIXED"; // TRADE_MODE
  fixedTradeAmountUsdt: number; // FIXED_TRADE_AMOUNT_USDT
  sentimentSizingMultiplier: number; // SENTIMENT_SIZING_MULTIPLIER
  // Demo simulation parameters (from config.py BACKTEST_* defaults)
  feeRate: number;             // BACKTEST_FEE_RATE = 0.001
  baseSlippagePct: number;     // BACKTEST_BASE_SLIPPAGE_PCT = 0.0005
  volumeFactor: number;        // BACKTEST_VOLUME_FACTOR = 0.000001
  maxDrawdownPct: number;      // BACKTEST_MAX_DRAWDOWN_PCT = 25
  minNotional: number;         // exchange MIN_NOTIONAL (demo: 5 USDT, Binance spot typical)
}

export const DEFAULT_CONFIG: StrategyConfig = {
  interval: "15m",
  atrPeriod: 14,
  atrTrendThreshold: 0.02,
  breakoutRrRatio: 2.5,
  baseRsiOversold: 30,
  baseRsiOverbought: 70,
  useBollingerBands: false,
  bbWindow: 20,
  bbWindowDev: 2.0,
  gridLevels: 3,
  gridStepPercent: 1.0,
  gridProfitTargetPercent: 1.5,
  gridInvalidationPercent: 2.0,
  sentimentThresholdPositive: 0.0,
  sentimentThresholdNegative: -0.1,
  fearGreedThreshold: 30,
  riskPerTradePercent: 1.0,
  tradeMode: "PERCENTAGE",
  fixedTradeAmountUsdt: 10.0,
  sentimentSizingMultiplier: 1.0,
  feeRate: 0.001,
  baseSlippagePct: 0.0005,
  volumeFactor: 0.000001,
  maxDrawdownPct: 25.0,
  minNotional: 5.0,
};

export interface Position {
  id: string;
  symbol: string;
  side: Side;
  strategy: StrategyName;
  entryPrice: number;
  qty: number;
  sl: number | null;           // breakout stop-loss
  tp: number | null;           // take-profit (breakout or grid level)
  invalidation: number | null; // grid invalidation price
  openedAt: number;
}

export interface Trade {
  id: string;
  ts: number;
  symbol: string;
  side: Side;
  qty: number;
  price: number;
  fee: number;
  pnl: number;                 // realized PnL on close (0 on open), matches PositionManager
  status: "FILLED" | "CLOSED" | "PLACED" | "PLACED_TP" | "HALTED";
  strategy: StrategyName | "risk";
}

export interface AccountState {
  ready: boolean;
  name: string;
  symbol: string;
  config: StrategyConfig;
  balance: number;             // free USDT (demo)
  initialBalance: number;
  equity: number;              // balance + unrealized
  peakEquity: number;
  realizedPnl: number;
  feesPaid: number;
  wins: number;
  losses: number;
  tradeCount: number;
  openPositions: Position[];
  recentTrades: Trade[];       // last 50, newest last
  equityHistory: { t: number; equity: number }[]; // last 240 points for the sparkline
  sentiment: number;
  fearGreed: number;
  regime: Regime;
  lastSignal: Signal;
  lastTick: number;
  ticks: number;
  paused: boolean;
  halted: boolean;             // drawdown guard tripped
  haltReason: string | null;
  lastError: string | null;
}
