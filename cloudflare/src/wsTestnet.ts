// Binance Spot TESTNET WebSocket API client. Uses a short-lived outbound
// WebSocket from the Worker: no HTTP POST, therefore no Binance WAF 1010.
// Docs: wss://ws-api.testnet.binance.vision/ws-api/v3; SIGNED params are
// sorted alphabetically as `k=v` pairs joined with &, HMAC-SHA256 hex signed
// with the secret key; apiKey and timestamp are part of the signed payload.
// The connection lives only for one request/response (well under the 24h
// connection limit and the server's 20s ping cadence).

import { signQuery } from "./testnet";

const WS_URL = "wss://ws-api.testnet.binance.vision/ws-api/v3";

export interface WsCreds {
  BINANCE_TESTNET_API_KEY?: string;
  BINANCE_TESTNET_SECRET?: string;
}

type Params = Record<string, string | number>;

export async function wsSignedRequest(
  method: string,
  params: Params,
  creds: WsCreds,
  timeoutMs = 15000,
): Promise<{ status: number; result?: any; error?: { code: number; msg: string } }> {
  if (!creds.BINANCE_TESTNET_API_KEY || !creds.BINANCE_TESTNET_SECRET) {
    throw new Error("testnet credentials not configured");
  }
  const id = crypto.randomUUID();
  const full: Params = {
    ...params,
    apiKey: creds.BINANCE_TESTNET_API_KEY,
    timestamp: Date.now(),
    recvWindow: 5000,
  };
  const sorted = Object.keys(full).sort().map((k) => `${k}=${String(full[k])}`).join("&");
  const signature = await signQuery(sorted, creds.BINANCE_TESTNET_SECRET);
  const message = JSON.stringify({ id, method, params: { ...full, signature } });

  return new Promise((resolve, reject) => {
    let ws: WebSocket;
    try { ws = new WebSocket(WS_URL); }
    catch (e) { reject(new Error(`ws open failed: ${String(e)}`)); return; }
    const timer = setTimeout(() => {
      try { ws.close(); } catch { /* already closed */ }
      reject(new Error("ws request timeout"));
    }, timeoutMs);
    ws.onopen = () => ws.send(message);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(String(ev.data));
        if (data?.id !== id) return; // ignore pings/unsolicited frames
        clearTimeout(timer);
        try { ws.close(); } catch { /* ignore */ }
        resolve(data);
      } catch { /* ignore non-JSON frames */ }
    };
    ws.onerror = () => {
      clearTimeout(timer);
      reject(new Error("ws connection error"));
    };
  });
}

export function wsMarketOrder(symbol: string, side: "BUY" | "SELL", quantity: number, creds: WsCreds) {
  return wsSignedRequest("order.place", {
    symbol, side, type: "MARKET", quantity: quantity.toFixed(8),
  }, creds);
}
