import express from "express";
import { fileURLToPath } from "node:url";
import { createAppFromEnv } from "./config.js";

const app = createAppFromEnv();
const dist = fileURLToPath(new URL("../dist", import.meta.url));

app.use(express.static(dist));
app.get("/{*path}", (req, res) => res.sendFile("index.html", { root: dist }));

const port = Number(process.env.PORT ?? 3000);
app.listen(port, () => console.log(`Sandoghche running on http://localhost:${port}`));
