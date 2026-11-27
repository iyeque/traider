const WORKER = "https://traider-cloudflare.mmmaximus18.workers.dev";
const ALLOWED = new Set(["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]);

module.exports = async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  if (!process.env.EXECUTOR_TOKEN || req.headers["x-executor-token"] !== process.env.EXECUTOR_TOKEN) {
    return res.status(401).json({ error: "unauthorized" });
  }
  const body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
  const { kind, symbol, side, quantity, takeProfit, stopLoss } = body;
  if (!ALLOWED.has(symbol) || (side !== "BUY" && side !== "SELL") || !(Number(quantity) > 0)) {
    return res.status(400).json({ error: "invalid order intent" });
  }
  try {
    const ir = await fetch(WORKER + "/api/executor/intent", {
      method: "POST",
      headers: { "content-type": "application/json", "x-executor-token": process.env.EXECUTOR_TOKEN },
      body: JSON.stringify({ kind, symbol, side, quantity, takeProfit, stopLoss }),
    });
    const intent = await ir.json();
    if (!intent.url) return res.status(400).json({ error: intent.error || "intent failed" });
    const r = await fetch(intent.url, { method: "POST", headers: { "X-MBX-APIKEY": intent.apiKey } });
    const data = await r.json();
    return res.status(200).json({
      binanceStatus: r.status,
      orderId: data.orderId ?? data.orderReportList?.[0]?.orderId,
      status: data.status,
      executedQty: data.executedQty,
      msg: data.msg,
    });
  } catch (e) {
    return res.status(502).json({ error: String(e).slice(0, 200) });
  }
};
