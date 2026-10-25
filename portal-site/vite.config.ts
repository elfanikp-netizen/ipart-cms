import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5174,
    strictPort: true,
    allowedHosts: ["raven-reclaim-capricorn.ngrok-free.dev", ".ngrok-free.dev"],
    proxy: {
      "/scrapper": {
        target: "http://localhost:5173",
        changeOrigin: true,
        ws: true,
      },
      "/api/auth": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/api/profile": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/api/users": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/api/activity": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});