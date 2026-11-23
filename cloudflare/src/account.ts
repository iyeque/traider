// TradingAccount — one Durable Object per demo account (btc-demo, eth-demo, ...).
// SQLite holds the full trade log; the State API syncs live state to dashboards.
// A 60s recurring schedule runs the strategy cycle (Python run_bot port).

import { Agent, callable } from "agents";
import type { Env } from "./env";
import type { AccountState, Candle, Position, StrategyConfig, Trade } from "./core/types";
import { DEFAULT_CONFIG } from "./core/types";
import { applyIndicators, atr as atrSeries } from "./core/indicators";
import { generateSignal, selectStrategy, calculateTradeSize, breakoutLevels, gridLadder, isMarketSafe } from "./core/strategy";
import { marketFill, realizedPnl, checkExit, gridBuyFilled, unrealizedPnl, drawdownPct, makeTrade } from "./core/sim";
import { fetchKlines } from "./market";
import { getLiveSentiment } from "./sentiment";

const SYMBOLS: Record<string, string> = { btc: "BTCUSDT", eth: "ETHUSDT", sol: "SOLUSDT", bnb: "BNBUSDT" };
const INITIAL_BALANCE = 1000; // BACKTEST_INITIAL_BALANCE

interface PendingGrid { levels: { buyPrice: number; qty: number; tpPrice: number }[]; invalidationPrice: number; placedAt: number; }

export class TradingAccount extends Agent<Env, AccountState> {
  initialState: AccountState = {
    ready: false, name: "demo", symbol: "BTCUSDT", config: { ...DEFAULT_CONFIG },
    balance: INITIAL_BALANCE, initialBalance: INITIAL_BALANCE, equity: INITIAL_BALANCE,
    peakEquity: INITIAL_BALANCE, realizedPnl: 0, feesPaid: 0, wins: 0, losses: 0, tradeCount: 0,
    openPositions: [], recentTrades: [], equityHistory: [],
    sentiment: 0, fearGreed: 50, regime: "unknown", lastSignal: null,
    lastTick: 0, ticks: 0, paused: false, halted: false, haltReason: null, lastError: null,
  };

  private pendingGrid: PendingGrid | null = null;

  async onStart() {
    this.sql`CREATE TABLE IF NOT EXISTS trades (
      id TEXT PRIMARY KEY, ts INTEGER, symbol TEXT, side TEXT, qty REAL,
      price REAL, fee REAL, pnl REAL, status TEXT, strategy TEXT
    )`;
    if (!this.state.ready) {
      const base = (this.name || "btc-demo").split("-")[0].toLowerCase();
      const symbol = SYMBOLS[base] ?? "BTCUSDT";
      this.setState({ ...this.initialState, ready: true, name: this.name, symbol });
    }
    // Recurring schedules are idempotent (one row however often the agent starts).
    await this.scheduleEvery(60, "tick");
  }

  async onRequest(request: Request): Promise<Response> {
    if (request.method === "POST") { await this.tick(); return Response.json(this.state); }
    return Response.json(this.state);
  }

  // ---- controls (RPC from the dashboard via useAgent stub) ----
  @callable() async pause() { this.setState({ ...this.state, paused: true }); return this.state.paused; }
  @callable() async resume() { this.setState({ ...this.state, paused: false }); return this.state.paused; }
  @callable() async forceTick() { await this.tick(); return this.state; }
  @callable() async updateConfig(patch: Partial<StrategyConfig>) {
    this.setState({ ...this.state, config: { ...this.state.config, ...patch } });
    return this.state.config;
  }
  @callable() async resetAccount() {
    this.sql`DELETE FROM trades`;
    this.pendingGrid = null;
    this.setState({
      ...this.initialState, ready: true, name: this.name, symbol: this.state.symbol,
      config: this.state.config,
    });
    return this.state;
  }

  // ---- the strategy cycle (port of main.py run_bot) ----
  async tick() {
    const s = this.state;
    if (!s.ready || s.paused) return;
    const cfg = s.config;
    const now = Date.now();
    try {
      const [candles, sent] = await Promise.all([
        fetchKlines(s.symbol, cfg.interval, 100),
        getLiveSentiment(this.env, s.symbol.replace("USDT", "")),
      ]);
      if (candles.length < 30) throw new Error("insufficient klines");
      const last = candles[candles.length - 1];
      const price = last.c;

      const ind = applyIndicators(candles, cfg.atrPeriod, cfg.useBollingerBands, cfg.bbWindow, cfg.bbWindowDev);
      const i = candles.length - 1;
      const atrLast = ind.atr[i];
      const regime = Number.isFinite(atrLast) ? (atrLast / price > cfg.atrTrendThreshold ? "trending" : "sideways") : "unknown";

      let positions = [...s.openPositions];
      let balance = s.balance;
      let realized = s.realizedPnl;
      let fees = s.feesPaid;
      let wins = s.wins, losses = s.losses, tradeCount = s.tradeCount;
      const newTrades: Trade[] = [];

      const closePos = (pos: Position, exitPrice: number, status: Trade["status"], strategy: Trade["strategy"]) => {
        const fill = marketFill(exitPrice, pos.side === "buy" ? "sell" : "buy", pos.qty, cfg);
        const pnl = realizedPnl(pos.entryPrice, fill.fillPrice, pos.qty, pos.side);
        balance += pos.qty * pos.entryPrice + pnl - fill.fee; // return reserved notional + pnl - fee
        realized += pnl; fees += fill.fee; tradeCount += 1;
        if (pnl >= 0) wins += 1; else losses += 1;
        const t = makeTrade({ ts: now, symbol: pos.symbol, side: pos.side === "buy" ? "sell" : "buy", qty: pos.qty, price: fill.fillPrice, fee: fill.fee, pnl, status, strategy });
        newTrades.push(t);
        this.sql`INSERT INTO trades (id, ts, symbol, side, qty, price, fee, pnl, status, strategy)
                 VALUES (${t.id}, ${t.ts}, ${t.symbol}, ${t.side}, ${t.qty}, ${t.price}, ${t.fee}, ${t.pnl}, ${t.status}, ${t.strategy})`;
        positions = positions.filter((p) => p.id !== pos.id);
      };

      // 1) manage open positions against the latest candle
      for (const pos of [...positions]) {
        const ex = checkExit(pos, last);
        if (ex.hit) closePos(pos, ex.exitPrice, "CLOSED", pos.strategy);
      }

      // 2) grid ladder fills / invalidation
      if (this.pendingGrid) {
        const pg = this.pendingGrid;
        if (last.l <= pg.invalidationPrice) {
          for (const pos of [...positions]) if (pos.strategy === "grid") closePos(pos, pg.invalidationPrice, "CLOSED", "grid");
          this.pendingGrid = null;
        } else {
          const remaining: typeof pg.levels = [];
          for (const lvl of pg.levels) {
            if (gridBuyFilled(lvl, last) && balance >= lvl.qty * lvl.buyPrice) {
              const fill = marketFill(lvl.buyPrice, "buy", lvl.qty, cfg);
              const cost = lvl.qty * fill.fillPrice + fill.fee;
              if (balance >= cost) {
                balance -= cost; fees += fill.fee; tradeCount += 1;
                const t = makeTrade({ ts: now, symbol: s.symbol, side: "buy", qty: lvl.qty, price: fill.fillPrice, fee: fill.fee, pnl: 0, status: "FILLED", strategy: "grid" });
                newTrades.push(t);
                this.sql`INSERT INTO trades (id, ts, symbol, side, qty, price, fee, pnl, status, strategy)
                         VALUES (${t.id}, ${t.ts}, ${t.symbol}, ${t.side}, ${t.qty}, ${t.price}, ${t.fee}, ${t.pnl}, ${t.status}, ${t.strategy})`;
                positions.push({ id: t.id, symbol: s.symbol, side: "buy", strategy: "grid", entryPrice: fill.fillPrice, qty: lvl.qty, sl: null, tp: lvl.tpPrice, invalidation: pg.invalidationPrice, openedAt: now });
              } else remaining.push(lvl);
            } else remaining.push(lvl);
          }
          this.pendingGrid = remaining.length ? { ...pg, levels: remaining } : null;
        }
      }

      // 3) safety gate + new entries (Python run_bot order)
      const gate = isMarketSafe(sent.sentiment, sent.fearGreed, cfg.sentimentThresholdPositive, cfg.fearGreedThreshold);
      let signal: AccountState["lastSignal"] = null;
      let halted = s.halted, haltReason = s.haltReason;

      if (gate.safe && regime !== "unknown" && !halted) {
        const strategy = selectStrategy(atrLast, price, cfg.atrTrendThreshold);
        if (strategy === "breakout") {
          signal = generateSignal({
            rsi: ind.rsi[i], macd: ind.macd[i], macdSignal: ind.macdSignal[i],
            sentiment: sent.sentiment,
            sentimentThresholdPositive: cfg.sentimentThresholdPositive,
            sentimentThresholdNegative: cfg.sentimentThresholdNegative,
            baseRsiOversold: cfg.baseRsiOversold, baseRsiOverbought: cfg.baseRsiOverbought,
            useBollingerBands: cfg.useBollingerBands,
            bbLower: ind.bbLower ? ind.bbLower[i] : null,
            bbUpper: ind.bbUpper ? ind.bbUpper[i] : null,
            currentClose: price,
          });
          if (signal && Number.isFinite(ind.rsi[i])) {
            const amount = calculateTradeSize(balance, cfg.tradeMode, cfg.riskPerTradePercent, sent.sentiment, cfg.fixedTradeAmountUsdt, cfg.sentimentSizingMultiplier);
            const m1 = await fetchKlines(s.symbol, "1m", 100);
            const a1 = atrSeries(m1.map((k) => k.h), m1.map((k) => k.l), m1.map((k) => k.c), cfg.atrPeriod);
            const atr1m = a1[a1.length - 1];
            if (Number.isFinite(atr1m) && atr1m > 0) {
              const { sl, tp, qty } = breakoutLevels(price, atr1m, cfg.breakoutRrRatio, signal, amount);
              const fill = marketFill(price, signal, qty, cfg);
              const cost = qty * fill.fillPrice + fill.fee;
              if (balance >= cost && qty * fill.fillPrice >= cfg.minNotional) {
                balance -= cost; fees += fill.fee; tradeCount += 1;
                const t = makeTrade({ ts: now, symbol: s.symbol, side: signal, qty, price: fill.fillPrice, fee: fill.fee, pnl: 0, status: "FILLED", strategy: "breakout" });
                newTrades.push(t);
                this.sql`INSERT INTO trades (id, ts, symbol, side, qty, price, fee, pnl, status, strategy)
                         VALUES (${t.id}, ${t.ts}, ${t.symbol}, ${t.side}, ${t.qty}, ${t.price}, ${t.fee}, ${t.pnl}, ${t.status}, ${t.strategy})`;
                positions.push({ id: t.id, symbol: s.symbol, side: signal, strategy: "breakout", entryPrice: fill.fillPrice, qty, sl, tp, invalidation: null, openedAt: now });
              }
            }
          }
        } else if (!this.pendingGrid && positions.filter((p) => p.strategy === "grid").length === 0) {
          // grid regime: ladder sized off balance (sentiment not used for grid sizing — Python)
          const amount = calculateTradeSize(balance, cfg.tradeMode, cfg.riskPerTradePercent, 0, cfg.fixedTradeAmountUsdt, 0);
          const ladder = gridLadder(price, amount, cfg.gridLevels, cfg.gridStepPercent, cfg.gridProfitTargetPercent, cfg.gridInvalidationPercent, cfg.minNotional);
          if (ladder.ok) this.pendingGrid = { levels: ladder.levels, invalidationPrice: ladder.invalidationPrice, placedAt: now };
        }
      }

      // 4) equity + drawdown guard
      const reserved = positions.reduce((a, p) => a + p.qty * p.entryPrice, 0);
      const unreal = positions.reduce((a, p) => a + unrealizedPnl(p, price), 0);
      const equity = balance + reserved + unreal;
      const peak = Math.max(s.peakEquity, equity);
      const dd = drawdownPct(peak, equity);
      if (!halted && dd >= cfg.maxDrawdownPct) {
        halted = true; haltReason = `max drawdown ${dd.toFixed(1)}% >= ${cfg.maxDrawdownPct}% — flattened`;
        for (const pos of [...positions]) closePos(pos, price, "HALTED", "risk");
        this.pendingGrid = null;
      }

      const recentTrades = [...s.recentTrades, ...newTrades].slice(-50);
      const equityHistory = [...s.equityHistory, { t: now, equity }].slice(-240);
      this.setState({
        ...s, balance, equity, peakEquity: peak, realizedPnl: realized, feesPaid: fees,
        wins, losses, tradeCount, openPositions: positions, recentTrades, equityHistory,
        sentiment: sent.sentiment, fearGreed: sent.fearGreed, regime, lastSignal: signal,
        lastTick: now, ticks: s.ticks + 1, halted, haltReason, lastError: gate.safe ? null : gate.reason,
      });
    } catch (e) {
      this.setState({ ...this.state, lastError: String(e instanceof Error ? e.message : e), lastTick: now, ticks: this.state.ticks + 1 });
    }
  }
}
