import express from "express";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createAppFromEnv } from "./config.js";

const app = createAppFromEnv();
const dist = fileURLToPath(new URL("../dist", import.meta.url));

for (const page of ["index.html", "app/index.html", "404.html"]) {
  if (!existsSync(`${dist}/${page}`)) console.error(`Missing ${dist}/${page}: was \`npm run build\` run?`);
}

// Plain-http visits (e.g. typing the bare domain) go to https. Only when the
// platform's proxy says the request came in over http, so this can't loop.
app.use((req, res, next) => {
  if (req.headers["x-forwarded-proto"] === "http") {
    return res.redirect(301, `https://${req.headers.host}${req.originalUrl}`);
  }
  next();
});

// Hashed build assets never change, so browsers may keep them for a year.
app.use("/assets", express.static(`${dist}/assets`, { immutable: true, maxAge: "1y" }));
app.use(express.static(dist, { maxAge: "1h" }));

// The landing page and the app, spelled out so they never depend on
// directory-index handling.
app.get("/", (req, res) => res.sendFile("index.html", { root: dist }));
app.get(["/app", "/app/{*path}"], (req, res) => res.sendFile("app/index.html", { root: dist }));
app.use((req, res) => {
  console.warn(`404 ${req.method} ${req.originalUrl}`);
  res.status(404).sendFile("404.html", { root: dist });
});

// Draws run on their scheduled day (see src/lib/schedule.js).
setInterval(() => app.locals.runScheduledJobs().catch((e) => console.error(e)), 60 * 1000);

const port = Number(process.env.PORT ?? 3000);
const server = app.listen(port, () => console.log(`Digi Gharz listening on port ${port}`));

// Containers stop with SIGTERM; finish in-flight requests, then exit.
process.on("SIGTERM", () => server.close(() => process.exit(0)));
