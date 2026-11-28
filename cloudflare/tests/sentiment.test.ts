import { describe, it, expect } from "vitest";
import { dedupeHeadlines, aggregateScores, polarity, normalizeHeadline } from "../src/sentiment";

describe("multi-source sentiment aggregation", () => {
  it("deduplicates headlines across sources", () => {
    expect(dedupeHeadlines(["Bitcoin Rallies!", "bitcoin rallies!", "ETH falls"]))
      .toEqual(["Bitcoin Rallies!", "ETH falls"]);
  });
  it("normalizes headlines for dedup keys", () => {
    expect(normalizeHeadline("Bitcoin   RALLIES!!")).toBe("bitcoin rallies");
  });
  it("weights non-zero source scores", () => {
    const a = aggregateScores([
      { name: "gdelt", score: 0.2, weight: 1 },
      { name: "rss1", score: -0.2, weight: 1 },
      { name: "rss2", score: 0, weight: 0.8 },
    ]);
    expect(a.value).toBeCloseTo(0, 5);
    expect(a.sources).toBe(2);
    expect(a.bySource).toEqual({ gdelt: 0.2, rss1: -0.2 });
  });
  it("scores polarity with negators", () => {
    expect(polarity("good news")).toBeGreaterThan(0);
    expect(polarity("not good news")).toBeLessThan(0);
  });
});
