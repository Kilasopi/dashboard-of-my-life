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
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});