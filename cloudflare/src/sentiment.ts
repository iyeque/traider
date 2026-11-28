// Multi-source headline sentiment for Traider.
// Sources: CryptoPanic (if key), NewsAPI (if key), GDELT DOC (keyless),
// and several RSS feeds. Fear & Greed stays a separate input, never a
// substitute for headlines. Every source is scored with the same AFINN-165
// static lexifier (a port of the `sentiment` npm package), deduplicated by
// normalized headline, and combined with per-source weights. Freshness and
// source counts are returned so callers can refuse to trade on stale data.
//
// DOCUMENTED DEVIATION: Python scores headlines with TextBlob; the Worker uses
// AFINN-165. Scores differ slightly. Re-tune after changing this pipeline.

import labels from "./core/sentiment-en/labels.json";
import negatorsJson from "./core/sentiment-en/negators.json";

const LABELS = labels as Record<string, number>;
const NEGATORS = new Set(Object.keys(negatorsJson as Record<string, number>));

export interface SentimentResult {
  sentiment: number;
  fearGreed: number;
  sources: number;
  articles: number;
  stale: boolean;
  ageMinutes: number;
  bySource: Record<string, number>;
  proxy: boolean;
}

function tokenize(input: string): string[] {
  return input.toLowerCase()
    .replace(/\n/g, " ")
    .replace(/[.,\/#!$%\^&\*;:{}=_`\"~()]/g, " ")
    .replace(/\s\s+/g, " ")
    .trim()
    .split(" ");
}

export function polarity(text: string): number {
  try {
    const tokens = tokenize(text);
    let score = 0;
    for (let i = 0; i < tokens.length; i++) {
      let s = LABELS[tokens[i]] ?? 0;
      if (i > 0 && NEGATORS.has(tokens[i - 1])) s = -s;
      score += s;
    }
    return tokens.length ? score / tokens.length : 0;
  } catch { return 0; }
}

export function normalizeHeadline(title: string): string {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().slice(0, 90);
}

export function dedupeHeadlines(headlines: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const h of headlines) {
    const key = normalizeHeadline(h);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(h);
  }
  return out;
}

export function aggregateScores(scores: { name: string; score: number; weight: number }[]) {
  const valid = scores.filter((s) => Number.isFinite(s.score) && s.score !== 0);
  const totalWeight = valid.reduce((a, s) => a + s.weight, 0);
  const bySource: Record<string, number> = {};
  for (const s of valid) bySource[s.name] = Number(s.score.toFixed(4));
  return {
    value: totalWeight ? valid.reduce((a, s) => a + s.score * s.weight, 0) / totalWeight : 0,
    sources: valid.length,
    bySource,
  };
}

async function getJson(url: string, timeout = 8000): Promise<any | null> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(timeout) });
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

let gdeltCache: { at: number; titles: string[] } | null = null;
let lastHeadlineAt = 0; // freshest successful source, for staleness

export async function fetchGdeltHeadlines(
  currency: string,
  proxy?: { url: string; token: string },
  max = 50,
): Promise<string[]> {
  // GDELT asks for no more than one request every 5 seconds; cache for 5 min.
  if (gdeltCache && Date.now() - gdeltCache.at < 5 * 60 * 1000) return gdeltCache.titles;
  const query = `${currency} OR bitcoin OR cryptocurrency`;
  const direct = `https://api.gdeltproject.org/api/v2/doc/doc?query=${encodeURIComponent(query)}&mode=artlist&maxrecords=${max}&format=json&timespan=1d&sort=datedesc`;
  let j = await getJson(direct, 10000);
  if (!j && proxy?.url && proxy.token) {
    // GDELT may be blocked from Cloudflare egress; use the Vercel executor.
    try {
      const r = await fetch(`${proxy.url.replace(/\/$/, "")}/api/gdelt?q=${encodeURIComponent(query)}`, {
        headers: { "x-executor-token": proxy.token }, signal: AbortSignal.timeout(12000),
      });
      if (r.ok) j = await r.json();
    } catch { /* keep empty */ }
  }
  const titles = (j?.articles ?? []).map((a: any) => String(a.title ?? "").trim()).filter(Boolean);
  if (titles.length) gdeltCache = { at: Date.now(), titles };
  return titles;
}

export async function fetchCryptoPanicHeadlines(apiKey: string | undefined, currency = "BTC"): Promise<string[]> {
  if (!apiKey) return [];
  const j = await getJson(`https://cryptopanic.com/api/v1/posts/?auth_token=${apiKey}&currencies=${currency}&public=true&page=1`);
  return (j?.results ?? []).map((it: any) => String(it.title ?? "")).filter(Boolean);
}

export async function fetchNewsApiHeadlines(apiKey: string | undefined): Promise<string[]> {
  if (!apiKey) return [];
  const j = await getJson(`https://newsapi.org/v2/everything?q=${encodeURIComponent("bitcoin OR crypto")}&language=en&sortBy=publishedAt&pageSize=20&apiKey=${apiKey}`);
  return (j?.articles ?? []).map((a: any) => String(a.title ?? "")).filter(Boolean);
}

const RSS_FEEDS = [
  "https://cointelegraph.com/rss",
  "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
  "https://bitcoinmagazine.com/feed",
  "https://decrypt.co/feed",
  "https://www.thenewscrypto.com/feed",
  "https://coinjournal.net/feed/",
];

export async function fetchRssHeadlines(feedUrl: string, maxItems = 15): Promise<string[]> {
  try {
    const res = await fetch(feedUrl, {
      signal: AbortSignal.timeout(8000),
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.0.0 Safari/537.36" },
    });
    if (!res.ok) return [];
    const xml = await res.text();
    const titles: string[] = [];
    const itemRe = /<item[\s\S]*?<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/title>/g;
    let m: RegExpExecArray | null;
    while ((m = itemRe.exec(xml)) !== null && titles.length < maxItems) titles.push(m[1].trim());
    return titles;
  } catch { return []; }
}

export async function fetchFearGreed(): Promise<number> {
  const j = await getJson("https://api.alternative.me/fng/?limit=1");
  const v = j?.data?.[0]?.value;
  return v === undefined ? 50 : parseInt(String(v), 10);
}

function scoreHeadlines(headlines: string[]): number {
  const scores = headlines.map(polarity).filter((s) => s !== 0);
  return scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
}

export async function getLiveSentiment(
  env: { CRYPTOPANIC_API_KEY?: string; NEWSAPI_KEY?: string; DEMO_PROXY_SENTIMENT?: string; SENTIMENT_STALE_MINUTES?: string; VERCEL_EXECUTOR_URL?: string; EXECUTOR_TOKEN?: string },
  currency = "BTC",
): Promise<SentimentResult> {
  const fearGreed = await fetchFearGreed();
  const [cp, na, gd, ...rss] = await Promise.all([
    fetchCryptoPanicHeadlines(env.CRYPTOPANIC_API_KEY, currency),
    fetchNewsApiHeadlines(env.NEWSAPI_KEY),
    fetchGdeltHeadlines(currency, env.VERCEL_EXECUTOR_URL && env.EXECUTOR_TOKEN
      ? { url: env.VERCEL_EXECUTOR_URL, token: env.EXECUTOR_TOKEN } : undefined),
    ...RSS_FEEDS.map((f) => fetchRssHeadlines(f)),
  ]);

  const sources: { name: string; headlines: string[]; weight: number }[] = [
    { name: "cryptopanic", headlines: cp, weight: 1.2 },
    { name: "newsapi", headlines: na, weight: 1.2 },
    { name: "gdelt", headlines: gd, weight: 1.0 },
    ...rss.map((h, i) => ({ name: `rss${i + 1}`, headlines: h, weight: 0.8 })),
  ];
  const scores = sources.map((s) => ({ name: s.name, score: scoreHeadlines(dedupeHeadlines(s.headlines)), weight: s.weight }));
  const agg = aggregateScores(scores);
  const allHeadlines = dedupeHeadlines(sources.flatMap((s) => s.headlines));
  if (allHeadlines.length) lastHeadlineAt = Date.now();
  const ageMinutes = lastHeadlineAt ? Math.round((Date.now() - lastHeadlineAt) / 60000) : 9999;
  const staleLimit = Number(env.SENTIMENT_STALE_MINUTES ?? 60);
  const stale = agg.sources === 0 || ageMinutes > staleLimit;

  if (agg.sources) {
    return { sentiment: agg.value, fearGreed, sources: agg.sources, articles: allHeadlines.length, stale, ageMinutes, bySource: agg.bySource, proxy: false };
  }
  if (env.DEMO_PROXY_SENTIMENT !== "false") {
    return { sentiment: (fearGreed - 50) / 50, fearGreed, sources: 0, articles: 0, stale: true, ageMinutes, bySource: {}, proxy: true };
  }
  return { sentiment: 0, fearGreed, sources: 0, articles: 0, stale: true, ageMinutes, bySource: {}, proxy: false };
}
