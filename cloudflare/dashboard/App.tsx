import { useState } from "react";
import { useAgent } from "agents/react";
import type { TradingAccount } from "../src/account";
import type { AccountState } from "../src/core/types";

const ACCOUNTS = [
  { name: "btc-demo", label: "BTC/USDT" },
  { name: "eth-demo", label: "ETH/USDT" },
  { name: "sol-demo", label: "SOL/USDT" },
  { name: "bnb-demo", label: "BNB/USDT" },
];

export default function App() {
  const [selected, setSelected] = useState(ACCOUNTS[0].name);
  return (
    <div className="shell">
      <header>
        <h1>TRAIDER <span>cloudflare demo</span></h1>
        <nav>
          {ACCOUNTS.map((a) => (
            <button key={a.name} className={a.name === selected ? "tab on" : "tab"} onClick={() => setSelected(a.name)}>
              {a.label}
            </button>
          ))}
        </nav>
      </header>
      <AccountView key={selected} name={selected} />
      <footer>
        Demo accounts simulate trades against live Binance public market data. No keys, no real orders.
        Each account is a Durable Object with its own SQLite ledger, ticking every 60s.
      </footer>
    </div>
  );
}

function AccountView({ name }: { name: string }) {
  const agent = useAgent<TradingAccount, AccountState>({ agent: "trading-account", name });
  const state = agent.state as AccountState | undefined;
  const [busy, setBusy] = useState(false);

  const call = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try { await fn(); } catch (e) { console.error(e); } finally { setBusy(false); }
  };

  if (!state || !state.ready) {
    return <div className="card">Connecting to {name}… (first wake initializes the account and schedules the 60s tick)</div>;
  }

  const winRate = state.wins + state.losses > 0 ? (state.wins / (state.wins + state.losses)) * 100 : 0;
  const pnlClass = state.realizedPnl >= 0 ? "pos" : "neg";

  return (
    <main>
      {state.halted && <div className="banner halt">HALTED — {state.haltReason}</div>}
      {state.paused && <div className="banner pause">PAUSED — ticks skipped until resumed</div>}
      {state.lastError && <div className="banner warn">gate: {state.lastError}</div>}

      <section className="cards">
        <Stat label="Equity" value={`$${state.equity.toFixed(2)}`} />
        <Stat label="Free balance" value={`$${state.balance.toFixed(2)}`} />
        <Stat label="Realized PnL" value={`$${state.realizedPnl.toFixed(2)}`} cls={pnlClass} />
        <Stat label="Win rate" value={`${winRate.toFixed(1)}%`} sub={`${state.wins}W / ${state.losses}L`} />
        <Stat label="Trades" value={String(state.tradeCount)} sub={`fees $${state.feesPaid.toFixed(2)}`} />
        <Stat label="Regime" value={state.regime} sub={`signal: ${state.lastSignal ?? "—"}`} />
        <Stat label="Sentiment" value={state.sentiment.toFixed(2)} sub={`Fear & Greed ${state.fearGreed}`} />
        <Stat label="Ticks" value={String(state.ticks)} sub={state.lastTick ? new Date(state.lastTick).toLocaleTimeString() : "—"} />
      </section>

      <section className="card">
        <h2>Equity</h2>
        <Sparkline points={state.equityHistory.map((p) => p.equity)} />
      </section>

      <section className="card">
        <h2>Open positions ({state.openPositions.length})</h2>
        <table>
          <thead><tr><th>Strategy</th><th>Side</th><th>Qty</th><th>Entry</th><th>SL</th><th>TP</th><th>Invalidation</th></tr></thead>
          <tbody>
            {state.openPositions.length === 0 && <tr><td colSpan={7} className="empty">flat</td></tr>}
            {state.openPositions.map((p) => (
              <tr key={p.id}>
                <td>{p.strategy}</td><td className={p.side === "buy" ? "pos" : "neg"}>{p.side}</td>
                <td>{p.qty.toFixed(6)}</td><td>{p.entryPrice.toFixed(2)}</td>
                <td>{p.sl?.toFixed(2) ?? "—"}</td><td>{p.tp?.toFixed(2) ?? "—"}</td>
                <td>{p.invalidation?.toFixed(2) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Recent trades</h2>
        <table>
          <thead><tr><th>Time</th><th>Side</th><th>Qty</th><th>Price</th><th>Fee</th><th>PnL</th><th>Status</th><th>Strategy</th></tr></thead>
          <tbody>
            {state.recentTrades.length === 0 && <tr><td colSpan={8} className="empty">no trades yet — the safety gate blocks entries when sentiment is bearish (faithful to the Python bot)</td></tr>}
            {[...state.recentTrades].reverse().slice(0, 15).map((t) => (
              <tr key={t.id}>
                <td>{new Date(t.ts).toLocaleTimeString()}</td>
                <td className={t.side === "buy" ? "pos" : "neg"}>{t.side}</td>
                <td>{t.qty.toFixed(6)}</td><td>{t.price.toFixed(2)}</td><td>{t.fee.toFixed(4)}</td>
                <td className={t.pnl >= 0 ? "pos" : "neg"}>{t.pnl ? t.pnl.toFixed(2) : "—"}</td>
                <td>{t.status}</td><td>{t.strategy}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card controls">
        <h2>Controls</h2>
        <div className="row">
          <button disabled={busy} onClick={() => call(() => agent.stub.forceTick())}>Tick now</button>
          {state.paused
            ? <button disabled={busy} onClick={() => call(() => agent.stub.resume())}>Resume</button>
            : <button disabled={busy} onClick={() => call(() => agent.stub.pause())}>Pause</button>}
          <button disabled={busy} className="danger" onClick={() => call(() => agent.stub.resetAccount())}>Reset account</button>
        </div>
        <ConfigPanel state={state} apply={(patch) => call(() => agent.stub.updateConfig(patch))} busy={busy} />
      </section>
    </main>
  );
}

function Stat({ label, value, sub, cls }: { label: string; value: string; sub?: string; cls?: string }) {
  return (
    <div className="stat card">
      <div className="label">{label}</div>
      <div className={`value ${cls ?? ""}`}>{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return <div className="empty">collecting equity points…</div>;
  const w = 800, h = 120;
  const min = Math.min(...points), max = Math.max(...points);
  const span = max - min || 1;
  const path = points.map((p, i) => `${(i / (points.length - 1)) * w},${h - ((p - min) / span) * (h - 10) - 5}`).join(" ");
  const up = points[points.length - 1] >= points[0];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="spark" preserveAspectRatio="none">
      <polyline points={path} fill="none" stroke={up ? "#2dd4a7" : "#e86a4a"} strokeWidth="2" />
    </svg>
  );
}

function ConfigPanel({ state, apply, busy }: { state: AccountState; apply: (p: Record<string, number | boolean>) => void; busy: boolean }) {
  const [minSent, setMinSent] = useState(String(state.config.sentimentThresholdPositive));
  const [risk, setRisk] = useState(String(state.config.riskPerTradePercent));
  const [bb, setBb] = useState(state.config.useBollingerBands);
  return (
    <div className="row config">
      <label>min sentiment <input value={minSent} onChange={(e) => setMinSent(e.target.value)} /></label>
      <label>risk % <input value={risk} onChange={(e) => setRisk(e.target.value)} /></label>
      <label className="check"><input type="checkbox" checked={bb} onChange={(e) => setBb(e.target.checked)} /> Bollinger</label>
      <button disabled={busy} onClick={() => apply({ sentimentThresholdPositive: Number(minSent), riskPerTradePercent: Number(risk), useBollingerBands: bb })}>
        Apply config
      </button>
    </div>
  );
}
