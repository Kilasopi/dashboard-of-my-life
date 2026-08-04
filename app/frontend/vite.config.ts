import path from "path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "localhost",
    port: 3000,
    strictPort: true,
    proxy: {
      // Trailing slash matters: "/system-health" is a frontend route, not an API
      // path, and a bare "/system" prefix would wrongly proxy it to the backend.
      "/system/": process.env.VITE_DEV_BACKEND_URL ?? "http://localhost:8000",
      "/programming/": process.env.VITE_DEV_BACKEND_URL ?? "http://localhost:8000",
      "/spotify/": process.env.VITE_DEV_BACKEND_URL ?? "http://localhost:8000",
      "/claude-usage/": process.env.VITE_DEV_BACKEND_URL ?? "http://localhost:8000",
      // The frontend page route and the backend API path are both literally
      // "/finances" (unlike the other cards, which use distinct names) - so this
      // matches on request *method* instead of path to avoid proxying a real page
      // load/refresh of the /finances page to the backend and getting raw JSON
      // back instead of the SPA.
      "/finances": {
        target: process.env.VITE_DEV_BACKEND_URL ?? "http://localhost:8000",
        bypass: (req) => (req.method === "GET" && req.headers.accept?.includes("text/html")
          ? req.url
          : undefined),
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});