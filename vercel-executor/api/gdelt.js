module.exports = async function handler(req, res) {
  if (!process.env.EXECUTOR_TOKEN || req.headers["x-executor-token"] !== process.env.EXECUTOR_TOKEN) {
    return res.status(401).json({ error: "unauthorized" });
  }
  const q = String(req.query.q || "bitcoin OR cryptocurrency").slice(0, 200);
  const url = "https://api.gdeltproject.org/api/v2/doc/doc?query=" + encodeURIComponent(q)
    + "&mode=artlist&maxrecords=50&format=json&timespan=1d&sort=datedesc";
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(12000) });
    if (!r.ok) return res.status(502).json({ error: "GDELT HTTP " + r.status });
    const data = await r.json();
    return res.status(200).json({ articles: (data.articles || []).map((a) => ({ title: a.title })) });
  } catch (e) {
    return res.status(502).json({ error: String(e).slice(0, 160) });
  }
};
