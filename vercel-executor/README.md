# Traider testnet execution plane

The Cloudflare Worker holds strategy, state and the Binance testnet keys, but
Binance's WAF blocks order requests from Cloudflare egress. This Vercel
function is the execution plane, pinned to `bom1` (Mumbai), an egress Binance
accepts. It never sees the API secret: the Worker signs a short-lived order
URL and the function posts it.

Deploy: `npx vercel deploy --prod --yes --regions bom1` with `EXECUTOR_TOKEN`
set as a Vercel environment variable. Requests need `x-executor-token`.
