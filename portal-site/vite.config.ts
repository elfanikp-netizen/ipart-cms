import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "redirect-mounted-app-roots",
      configureServer(server) {
        server.middlewares.use((request, response, next) => {
          if (request.method !== "GET" && request.method !== "HEAD") {
            next();
            return;
          }

          const requestUrl = new URL(request.url ?? "/", "http://localhost");
          if (requestUrl.pathname === "/scrapper" || requestUrl.pathname === "/universe") {
            response.statusCode = 308;
            response.setHeader("Location", `${requestUrl.pathname}/${requestUrl.search}`);
            response.end();
            return;
          }

          next();
        });
      },
    },
  ],
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
      "/universe": {
        target: "http://localhost:5175",
        changeOrigin: true,
        ws: true,
      },
      "/api/universe": {
        target: "http://localhost:8002",
        changeOrigin: true,
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