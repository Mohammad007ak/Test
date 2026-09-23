import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const page = (path) => fileURLToPath(new URL(path, import.meta.url));

// Public pages that belong in the sitemap, with their relative priority.
const SITEMAP = [
  { path: "/welcome/", priority: "1.0", changefreq: "weekly" },
  { path: "/guide/family-loan-fund/", priority: "0.8", changefreq: "monthly" },
  { path: "/terms/", priority: "0.3", changefreq: "yearly" },
];

// In development the API runs inside Vite's own server, so one
// `npm run dev` starts everything on a single port.
function apiServer() {
  return {
    name: "sandogh-api",
    async configureServer(server) {
      // Server settings (SMS keys, DEMO_MODE, ...) come from .env, as with `npm start`.
      try {
        process.loadEnvFile(".env");
      } catch {
        // No .env: dev defaults (codes shown on screen).
      }
      const { createAppFromEnv } = await server.ssrLoadModule("/server/config.js");
      const app = await createAppFromEnv();
      setInterval(() => app.locals.runScheduledJobs().catch((e) => console.error(e)), 60 * 1000);
      server.middlewares.use((req, res, next) => (req.url.startsWith("/api/") ? app(req, res, next) : next()));
      // Same URLs as production: the app at the root, the landing page at /welcome/.
      server.middlewares.use((req, res, next) => {
        const [path, query] = req.url.split("?");
        if (path === "/") req.url = `/app/${query ? `?${query}` : ""}`;
        else if (path === "/welcome" || path === "/welcome/") req.url = "/index.html";
        next();
      });
    },
  };
}

// Canonical URLs, Open Graph tags and the sitemap need the real domain.
// It comes from SITE_URL (see .env.example) and is baked in at build time.
function seo(siteUrl) {
  return {
    name: "sandogh-seo",
    transformIndexHtml: (html) => html.replaceAll("__SITE_URL__", siteUrl),
    generateBundle() {
      const today = new Date().toISOString().slice(0, 10);
      const urls = SITEMAP.map(
        (p) =>
          `  <url>\n    <loc>${siteUrl}${p.path}</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>${p.changefreq}</changefreq>\n    <priority>${p.priority}</priority>\n  </url>`,
      ).join("\n");
      this.emitFile({
        type: "asset",
        fileName: "sitemap.xml",
        source: `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`,
      });
      this.emitFile({
        type: "asset",
        fileName: "robots.txt",
        source: `User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: ${siteUrl}/sitemap.xml\n`,
      });
    },
  };
}

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const siteUrl = (env.SITE_URL || (command === "build" ? "" : "http://localhost:5173")).replace(/\/$/, "");
  if (!siteUrl) {
    console.warn("\n⚠  SITE_URL is not set; canonical links and the sitemap will use http://localhost:3000.\n");
  }

  return {
    plugins: [react(), apiServer(), seo(siteUrl || "http://localhost:3000")],
    build: {
      rollupOptions: {
        input: {
          landing: page("./index.html"),
          app: page("./app/index.html"),
          guide: page("./guide/family-loan-fund/index.html"),
          terms: page("./terms/index.html"),
          notFound: page("./404.html"),
        },
      },
    },
  };
});
