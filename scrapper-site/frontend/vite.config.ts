import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/scrapper/",
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: ["raven-reclaim-capricorn.ngrok-free.dev", ".ngrok-free.dev"],
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        cookieDomainRewrite: "localhost",
      },
    },
  },
});
