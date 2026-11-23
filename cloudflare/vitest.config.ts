import { defineConfig } from "vitest/config";

// Separate from vite.config.ts (which sets root=dashboard for the UI build).
// The fidelity suite runs in plain Node against src/core — no Workers runtime needed.
export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    environment: "node",
  },
});
