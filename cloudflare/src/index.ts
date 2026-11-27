// Worker entry: routes /agents/trading-account/:name to the TradingAccount DO,
// serves /api/accounts, and falls through to the built React dashboard (ASSETS).

import { routeAgentRequest } from "agents";
import type { Env } from "./env";
import { TestnetClient, signedIntent, type OrderIntent } from "./testnet";
export { TradingAccount } from "./account";

const ACCOUNTS = [
  { name: "btc-demo", symbol: "BTCUSDT" },
  { name: "eth-demo", symbol: "ETHUSDT" },
  { name: "sol-demo", symbol: "SOLUSDT" },
  { name: "bnb-demo", symbol: "BNBUSDT" },
];

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const agentResponse = await routeAgentRequest(request, env);
    if (agentResponse) return agentResponse;
    if (url.pathname === "/api/accounts") return Response.json(ACCOUNTS);
    if (url.pathname === "/api/executor/intent" && request.method === "POST") {
      if (!env.EXECUTOR_TOKEN || request.headers.get("x-executor-token") !== env.EXECUTOR_TOKEN) {
        return Response.json({ error: "unauthorized" }, { status: 401 });
      }
      if (env.ENABLE_TESTNET_ORDERS !== "true") {
        return Response.json({ error: "testnet orders disabled" }, { status: 403 });
      }
      try {
        const body = await request.json() as OrderIntent;
        return Response.json(await signedIntent(env, body));
      } catch (e) {
        return Response.json({ error: String(e instanceof Error ? e.message : e).slice(0, 180) }, { status: 400 });
      }
    }
    if (url.pathname === "/api/testnet/status") {
      const client = new TestnetClient(env);
      if (!client.configured) return Response.json({ configured: false }, { status: 503 });
      try { return Response.json({ configured: true, ...await client.account() }); }
      catch (e) { return Response.json({ configured: true, ok: false, error: String(e instanceof Error ? e.message : e).slice(0, 180) }, { status: 502 }); }
    }
    if (url.pathname === "/api/testnet/order" && request.method === "POST") {
      if (!env.ADMIN_TOKEN || request.headers.get("x-admin-token") !== env.ADMIN_TOKEN) {
        return Response.json({ error: "unauthorized" }, { status: 401 });
      }
      const body = await request.json() as { side?: string; quantity?: number };
      const side = body.side?.toUpperCase();
      if ((side !== "BUY" && side !== "SELL") || !body.quantity || body.quantity <= 0) {
        return Response.json({ error: "side and positive quantity required" }, { status: 400 });
      }
      if (env.ENABLE_TESTNET_ORDERS !== "true") {
        return Response.json({ error: "testnet order placement disabled (ENABLE_TESTNET_ORDERS)" }, { status: 400 });
      }
      try {
        const o = await new TestnetClient(env).marketOrder("BTCUSDT", side, body.quantity);
        return Response.json(o);
      } catch (e) { return Response.json({ error: String(e instanceof Error ? e.message : e).slice(0, 180) }, { status: 400 }); }
    }
    if (url.pathname.startsWith("/api/")) return Response.json({ error: "not found" }, { status: 404 });
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
