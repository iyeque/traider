import { describe, it, expect } from "vitest";
import { createHmac } from "node:crypto";
import { encodeParams, signQuery, TestnetClient } from "../src/testnet";

describe("Binance testnet signing (verified against Node HMAC)", () => {
  it("encodes params deterministically", () => {
    expect(encodeParams({ symbol: "BTCUSDT", timestamp: 123, recvWindow: 5000 }))
      .toBe("symbol=BTCUSDT&timestamp=123&recvWindow=5000");
  });
  it("signQuery matches HMAC-SHA256 of the exact query string", async () => {
    const q = "symbol=BTCUSDT&side=BUY&timestamp=1700000000000";
    const expected = createHmac("sha256", "test-secret").update(q).digest("hex");
    expect(await signQuery(q, "test-secret")).toBe(expected);
  });
  it("matches HMAC-SHA256 for the Binance WS sorted-payload format", async () => {
    const payload = "apiKey=YOUR_API_KEY&price=52000.00&quantity=0.01000000&recvWindow=100&side=SELL&symbol=BTCUSDT&timeInForce=GTC&timestamp=1645423376532&type=LIMIT";
    // OpenSSL and Python both yield d7ab... for this payload/secret; the hash
    // printed in Binance's illustrative docs example (aa1b...) is stale.
    expect(await signQuery(payload, "YOUR_SECRET_KEY"))
      .toBe("d7ab7164420657782715adc22ec709eb55da95ae9296d2a224bdf3d08caa0967");
  });
  it("credentials and order opt-in flags reported honestly", () => {
    const bare = new TestnetClient({});
    expect(bare.configured).toBe(false);
    expect(bare.ordersEnabled).toBe(false);
    const full = new TestnetClient({
      BINANCE_TESTNET_API_KEY: "k", BINANCE_TESTNET_SECRET: "s", ENABLE_TESTNET_ORDERS: "true",
    });
    expect(full.configured).toBe(true);
    expect(full.ordersEnabled).toBe(true);
  });
});
