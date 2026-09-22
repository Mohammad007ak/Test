import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the API runs inside Vite's own server, so one
// `npm run dev` starts everything on a single port.
function apiServer() {
  return {
    name: "sandogh-api",
    async configureServer(server) {
      const { createAppFromEnv } = await server.ssrLoadModule("/server/config.js");
      const app = createAppFromEnv();
      server.middlewares.use((req, res, next) => (req.url.startsWith("/api/") ? app(req, res, next) : next()));
    },
  };
}

export default defineConfig({
  plugins: [react(), apiServer()],
});
