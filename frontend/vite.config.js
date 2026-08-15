import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Honour PORT when the environment assigns one; 5173 is just the default.
    port: Number(process.env.PORT) || 5173,
    // Why the frontend can always call a relative /api/... path: in dev this
    // proxies to Flask, and in production the SPA and API share one Vercel
    // origin. No hardcoded host anywhere, and no CORS in either environment.
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.js",
  },
});
