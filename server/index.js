import express from "express";
import { fileURLToPath } from "node:url";
import { createAppFromEnv } from "./config.js";

const app = createAppFromEnv();
const dist = fileURLToPath(new URL("../dist", import.meta.url));

// Hashed build assets never change, so browsers may keep them for a year.
app.use("/assets", express.static(`${dist}/assets`, { immutable: true, maxAge: "1y" }));
app.use(express.static(dist, { maxAge: "1h" }));

// The app is a single page under /app; everything else is a static page.
app.get("/app/{*path}", (req, res) => res.sendFile("app/index.html", { root: dist }));
app.use((req, res) => res.status(404).sendFile("404.html", { root: dist }));

const port = Number(process.env.PORT ?? 3000);
app.listen(port, () => console.log(`Digi Gharz running on http://localhost:${port}`));
