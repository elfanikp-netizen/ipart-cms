import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/universe/",
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5175,
    strictPort: true,
    proxy: {
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
      "/api/universe": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
    },
  },
});