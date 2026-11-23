// Worker entry: routes /agents/trading-account/:name to the TradingAccount DO,
// serves /api/accounts, and falls through to the built React dashboard (ASSETS).

import { routeAgentRequest } from "agents";
import type { Env } from "./env";
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
    if (url.pathname.startsWith("/api/")) return Response.json({ error: "not found" }, { status: 404 });
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
