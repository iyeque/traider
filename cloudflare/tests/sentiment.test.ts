import { describe, it, expect } from "vitest";
import { getLiveSentiment, fetchFearGreed } from "../src/sentiment";

// The scorer itself is module-private; exercise it through the exported
// aggregation with stubbed global fetch (no network, deterministic).
function stubFetch(impl: (url: string) => any) {
  (globalThis as any).fetch = impl;
}

describe("static AFINN polarity (bundles in Workers)", () => {
  it("no keys + no headlines -> Fear & Greed proxy", async () => {
    stubFetch(async (url: string) => ({
      ok: true, status: 200,
      json: async () => url.includes("alternative.me") ? { data: [{ value: "70" }] } : { results: [], articles: [] },
      text: async () => "",
    }));
    const r = await getLiveSentiment({ DEMO_PROXY_SENTIMENT: "true" }, "BTC");
    expect(r.fearGreed).toBe(70);
    expect(r.sentiment).toBeCloseTo(0.4, 6); // (70-50)/50
    expect(r.proxy).toBe(true);
  });

  it("NewsAPI headline scores aggregate (AFINN)", async () => {
    stubFetch(async (url: string) => ({
      ok: true, status: 200,
      json: async () => url.includes("alternative.me")
        ? { data: [{ value: "50" }] }
        : { articles: [{ title: "Great profit surge" }, { title: "Terrible fraud scandal" }] },
      text: async () => "",
    }));
    const r = await getLiveSentiment({ NEWSAPI_KEY: "test-key" }, "BTC");
    // Exact AFINN comparatives (verified against the npm `sentiment` package in Node):
    // "Great profit surge" = 1.6666666666666667, "Terrible fraud scandal" = -3.3333333333333335
    expect(r.proxy).toBe(false);
    expect(r.sentiment).toBeCloseTo(-0.8333333333333334, 6);
  });

  it("Fear & Greed failure degrades to neutral 50", async () => {
    stubFetch(async () => { throw new Error("offline"); });
    expect(await fetchFearGreed()).toBe(50);
  });
});
