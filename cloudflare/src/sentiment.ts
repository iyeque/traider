// Port of data_acquisition/fetch_live_sentiment.py + bot/sentiment_engine.py.
// Aggregation order is faithful: CryptoPanic -> NewsAPI -> RSS (only if <2
// non-zero sources) -> average of non-zero scores; Fear & Greed always fetched
// (neutral 50 on failure).
//
// DOCUMENTED DEVIATION: Python scores headlines with TextBlob (pattern lexicon).
// TextBlob has no JS port, so we use the AFINN-165 lexicon (`sentiment` npm,
// .comparative in [-1,1]). Same shape, different lexicon — scores will differ
// slightly from the Python bot.
//
// DEMO PROXY: with no API keys configured, real headline sentiment is usually
// 0 (neutral), which blocks all buys at the default threshold. For demo mode
// we derive sentiment from the public Fear & Greed index: (fng-50)/50.
// Disable with DEMO_PROXY_SENTIMENT="false".

// Static port of the `sentiment` npm package's English analyzer.
// The package itself does `require('../languages/' + languageCode + '/index')`
// at runtime, which esbuild cannot bundle into a Worker. We bundle the exact
// same AFINN labels + negators as static JSON and reproduce its tokenize/score
// algorithm (emojis omitted — irrelevant for news headlines).
import labels from "./core/sentiment-en/labels.json";
import negatorsJson from "./core/sentiment-en/negators.json";

const LABELS = labels as Record<string, number>;
const NEGATORS = new Set(Object.keys(negatorsJson as Record<string, number>));

function tokenize(input: string): string[] {
  return input.toLowerCase()
    .replace(/\n/g, " ")
    .replace(/[.,\/#!?$%\^&\*;:{}=_`\"~()]/g, " ")
    .replace(/\s\s+/g, " ")
    .trim()
    .split(" ");
}

function polarity(text: string): number {
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

async function getJson(url: string): Promise<any | null> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function fetchCryptoPanic(apiKey: string | undefined, currency = "BTC"): Promise<number> {
  if (!apiKey) return 0;
  const j = await getJson(`https://cryptopanic.com/api/v1/posts/?auth_token=${apiKey}&currencies=${currency}&public=true&page=1`);
  const items = j?.results ?? [];
  const scores = items.map((it: any) => polarity(String(it.title ?? ""))).filter((s: number) => s !== 0);
  return scores.length ? scores.reduce((a: number, b: number) => a + b, 0) / scores.length : 0;
}

export async function fetchNewsApi(apiKey: string | undefined): Promise<number> {
  if (!apiKey) return 0;
  const j = await getJson(`https://newsapi.org/v2/everything?q=${encodeURIComponent("bitcoin OR crypto")}&language=en&sortBy=publishedAt&pageSize=10&apiKey=${apiKey}`);
  const heads = (j?.articles ?? []).map((a: any) => String(a.title ?? "")).filter(Boolean);
  if (!heads.length) return 0;
  return heads.reduce((s: number, h: string) => s + polarity(h), 0) / heads.length;
}

const RSS_FEEDS = [
  "https://cointelegraph.com/rss",
  "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
  "https://feeds.feedburner.com/CoinDesk",
  "https://bitcoinmagazine.com/feed",
];

export async function fetchRssSentiment(feedUrl: string, maxItems = 10): Promise<number> {
  try {
    const res = await fetch(feedUrl, {
      signal: AbortSignal.timeout(8000),
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36" },
    });
    if (!res.ok) return 0;
    const xml = await res.text();
    const titles: string[] = [];
    const itemRe = /<item[\s\S]*?<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/title>/g;
    let m: RegExpExecArray | null;
    while ((m = itemRe.exec(xml)) !== null && titles.length < maxItems) titles.push(m[1].trim());
    if (!titles.length) return 0;
    return titles.reduce((s, t) => s + polarity(t), 0) / titles.length;
  } catch { return 0; }
}

export async function fetchFearGreed(): Promise<number> {
  const j = await getJson("https://api.alternative.me/fng/");
  const v = j?.data?.[0]?.value;
  return v === undefined ? 50 : parseInt(String(v), 10);
}

export async function getLiveSentiment(env: { CRYPTOPANIC_API_KEY?: string; NEWSAPI_KEY?: string; DEMO_PROXY_SENTIMENT?: string }, currency = "BTC"):
  Promise<{ sentiment: number; fearGreed: number; sources: number; proxy: boolean }> {
  const fearGreed = await fetchFearGreed();
  const scores: number[] = [];
  const cp = await fetchCryptoPanic(env.CRYPTOPANIC_API_KEY, currency);
  if (cp !== 0) scores.push(cp);
  const na = await fetchNewsApi(env.NEWSAPI_KEY);
  if (na !== 0) scores.push(na);
  if (scores.length < 2) {
    for (const feed of RSS_FEEDS) {
      const s = await fetchRssSentiment(feed);
      if (s !== 0) scores.push(s);
    }
  }
  if (scores.length) {
    return { sentiment: scores.reduce((a, b) => a + b, 0) / scores.length, fearGreed, sources: scores.length, proxy: false };
  }
  // No headline data (no keys / feeds blocked): demo proxy from Fear & Greed.
  if (env.DEMO_PROXY_SENTIMENT !== "false") {
    return { sentiment: (fearGreed - 50) / 50, fearGreed, sources: 0, proxy: true };
  }
  return { sentiment: 0, fearGreed, sources: 0, proxy: false };
}
