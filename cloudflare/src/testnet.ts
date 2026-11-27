// Binance Spot TESTNET signed REST client. Testnet only — mainnet is never
// referenced here. Signing uses Web Crypto HMAC-SHA256 (Workers native).
// Docs: base https://testnet.binance.vision/api, SIGNED endpoints need
// X-MBX-APIKEY header, timestamp, recvWindow (default 5000 ms), and hex HMAC
// of the query string. Keys and secrets stay in Worker secrets (env), never
// in code, logs, or client-synced state.

const BASE = "https://testnet.binance.vision";

export interface TestnetEnv {
  BINANCE_TESTNET_API_KEY?: string;
  BINANCE_TESTNET_SECRET?: string;
  ENABLE_TESTNET_ORDERS?: string; // opt-in flag for order placement
}

export interface AccountSummary {
  ok: true;
  canTrade: boolean;
  freeUsdt: number;
  assetCount: number;
  serverTime: number;
}

type Params = Record<string, string | number>;

export function encodeParams(params: Params): string {
  return new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();
}

export async function signQuery(query: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(query));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Signed order intent for the external execution plane (Vercel). Keys stay
// in Worker secrets; the Vercel function only receives a short-lived signed
// URL. Amounts are capped and symbols whitelisted even if the token leaks.
export interface OrderIntent {
  kind: "market" | "oco";
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  takeProfit?: number;
  stopLoss?: number;
}
export async function signedIntent(env: TestnetEnv, intent: OrderIntent): Promise<{ url: string; apiKey: string }> {
  if (!env.BINANCE_TESTNET_API_KEY || !env.BINANCE_TESTNET_SECRET) throw new Error("credentials not configured");
  if (!["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"].includes(intent.symbol)) throw new Error("symbol not allowed");
  const qty = Number(intent.quantity);
  if (!(qty > 0) || qty > 0.01) throw new Error("quantity out of range");
  const side = intent.side === "SELL" ? "SELL" : "BUY";
  const params: Params = { symbol: intent.symbol, side, quantity: qty.toFixed(8) };
  let path = "/api/v3/order";
  if (intent.kind === "oco") {
    const tp = Number(intent.takeProfit), sl = Number(intent.stopLoss);
    if (!(tp > 0) || !(sl > 0)) throw new Error("takeProfit and stopLoss required");
    path = "/api/v3/ocoOrder";
    params.price = tp.toFixed(8);
    params.stopPrice = sl.toFixed(8);
    params.stopLimitPrice = sl.toFixed(8);
    params.stopLimitTimeInForce = "GTC";
  } else {
    params.type = "MARKET";
  }
  params.timestamp = Date.now();
  params.recvWindow = 5000;
  const q = encodeParams(params);
  return { url: `${BASE}${path}?${q}&signature=${await signQuery(q, env.BINANCE_TESTNET_SECRET)}`, apiKey: env.BINANCE_TESTNET_API_KEY };
}

export class TestnetClient {
  constructor(private readonly env: TestnetEnv) {}

  get configured(): boolean {
    return !!(this.env.BINANCE_TESTNET_API_KEY && this.env.BINANCE_TESTNET_SECRET);
  }

  get ordersEnabled(): boolean {
    return this.env.ENABLE_TESTNET_ORDERS === "true";
  }

  private async viaExecutor(intent: OrderIntent): Promise<any> {
    const url = (this.env as TestnetEnv & { VERCEL_EXECUTOR_URL?: string; EXECUTOR_TOKEN?: string }).VERCEL_EXECUTOR_URL;
    const token = (this.env as TestnetEnv & { VERCEL_EXECUTOR_URL?: string; EXECUTOR_TOKEN?: string }).EXECUTOR_TOKEN;
    if (!url || !token) throw new Error("execution plane not configured");
    const res = await fetch(`${url.replace(/\/$/, "")}/api/order`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-executor-token": token },
      body: JSON.stringify(intent),
      signal: AbortSignal.timeout(20000),
    });
    const data: any = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(`executor HTTP ${res.status}: ${data?.error ?? "rejected"}`);
    if (data?.binanceStatus !== 200) throw new Error(`binance ${data?.binanceStatus ?? "?"}: ${data?.msg ?? "rejected"}`);
    return data;
  }

  private async request(method: string, path: string, params: Params = {}, signed = false): Promise<any> {
    const query = encodeParams(params);
    const url = `${BASE}${path}${query ? `?${query}` : ""}`;
    const headers: Record<string, string> = {
      Accept: "application/json",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9",
      Origin: "https://testnet.binance.vision",
      Referer: "https://testnet.binance.vision/",
    };
    if (signed) {
      if (!this.configured) throw new Error("testnet credentials not configured");
      headers["X-MBX-APIKEY"] = this.env.BINANCE_TESTNET_API_KEY!;
    }
    const res = await fetch(url, { method, headers, signal: AbortSignal.timeout(12000) });
    const text = await res.text();
    let data: any;
    try { data = JSON.parse(text); } catch { data = { raw: text.slice(0, 200) }; }
    if (!res.ok) {
      // Never echo the query (it contains the signature) or credentials.
      throw new Error(`testnet ${path} HTTP ${res.status}: ${data?.msg ?? "request rejected"}`);
    }
    return data;
  }

  private async signed(method: string, path: string, params: Params = {}): Promise<any> {
    const full: Params = { ...params, timestamp: Date.now(), recvWindow: 5000 };
    const query = encodeParams(full);
    full.signature = await signQuery(query, this.env.BINANCE_TESTNET_SECRET!);
    return this.request(method, path, full, true);
  }

  // USER_DATA — proves the key works without placing anything.
  async account(): Promise<AccountSummary> {
    const a = await this.signed("GET", "/api/v3/account", {});
    const balances = Array.isArray(a.balances) ? a.balances : [];
    return {
      ok: true,
      canTrade: !!a.canTrade,
      freeUsdt: Number(balances.find((b: any) => b.asset === "USDT")?.free ?? 0),
      assetCount: balances.length,
      serverTime: Date.now(),
    };
  }

  // Public exchange filters for quantity precision / min notional.
  async exchangeInfo(symbol: string): Promise<{ minNotional: number; stepSize: number; tickSize: number }> {
    const info = await this.request("GET", "/api/v3/exchangeInfo", { symbol });
    const s = info.symbols?.[0];
    const filters = s?.filters ?? [];
    const find = (type: string) => filters.find((f: any) => f.filterType === type) ?? {};
    return {
      minNotional: Number(find("NOTIONAL").minNotional ?? find("MIN_NOTIONAL").minNotional ?? 5),
      stepSize: Number(find("LOT_SIZE").stepSize ?? 1e-8),
      tickSize: Number(find("PRICE_FILTER").tickSize ?? 1e-8),
    };
  }

  // TRADE — explicit opt-in only (ENABLE_TESTNET_ORDERS=true).
  async marketOrder(symbol: string, side: "BUY" | "SELL", quantity: number): Promise<{ orderId: number; status: string; fills: number }> {
    if (!this.ordersEnabled) throw new Error("testnet order placement disabled (ENABLE_TESTNET_ORDERS)");
    const o = await this.viaExecutor({ kind: "market", symbol, side, quantity });
    return { orderId: Number(o.orderId), status: String(o.status), fills: 0 };
  }

  async ocoOrder(symbol: string, side: "BUY" | "SELL", quantity: number, tp: number, sl: number):
    Promise<{ orderId: number; status: string }> {
    if (!this.ordersEnabled) throw new Error("testnet order placement disabled (ENABLE_TESTNET_ORDERS)");
    const o = await this.viaExecutor({ kind: "oco", symbol, side, quantity, takeProfit: tp, stopLoss: sl });
    return { orderId: Number(o.orderId), status: String(o.status) };
  }

  async myTrades(symbol: string, fromId = 0): Promise<any[]> {
    const t = await this.signed("GET", "/api/v3/myTrades", { symbol, fromId, limit: 50 });
    return Array.isArray(t) ? t : [];
  }

  async cancelOrder(symbol: string, orderId: number): Promise<void> {
    await this.signed("DELETE", "/api/v3/order", { symbol, orderId });
  }
}
