import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dashboard lives in dashboard/, builds to dist/ (served by the Worker's ASSETS binding).
// In dev, /agents/* (incl. WebSockets) is proxied to `wrangler dev` on :8787.
export default defineConfig({
  root: "dashboard",
  plugins: [react()],
  build: { outDir: "../dist", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: {
      "/agents": { target: "http://localhost:8787", ws: true, changeOrigin: true },
      "/api": { target: "http://localhost:8787", changeOrigin: true },
    },
  },
});
