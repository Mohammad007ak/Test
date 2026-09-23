import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { openDatabase } from "./db.js";

// In a container, only a mounted disk survives a redeploy. Linux lists
// mounts in /proc/mounts; the database is safe if its folder, or a folder
// above it (other than /), is one of them. null when we can't tell.
function onMountedDisk(dbPath) {
  let mounts;
  try {
    mounts = readFileSync("/proc/mounts", "utf8")
      .split("\n")
      .map((line) => line.split(" ")[1])
      .filter(Boolean);
  } catch {
    return null;
  }
  for (let dir = dirname(resolve(dbPath)); dir !== "/"; dir = dirname(dir)) {
    if (mounts.includes(dir)) return true;
  }
  return false;
}
import { createSmsSender } from "./sms.js";
import { createApp } from "./app.js";
import { createDigipay } from "./digipay/index.js";

// Shared by the production server and the Vite dev middleware.
export function createAppFromEnv(env = process.env) {
  const production = env.NODE_ENV === "production";
  const dbPath = env.DB_PATH ?? "data/sandogh.db";
  const db = openDatabase(dbPath);
  const persistentStorage = production ? onMountedDisk(dbPath) : null;
  if (persistentStorage === false) {
    console.warn(
      `⚠ The database (${resolve(dbPath)}) is not on a mounted disk: all data will be lost on the next deploy. ` +
        `Mount a persistent disk at ${dirname(resolve(dbPath))}, or point DB_PATH at the disk you mounted.`,
    );
  }
  const sendCode = createSmsSender(env);
  const opsPhones = (env.OPS_PHONES ?? "")
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);
  // How long a circle may wait to fill. The goal is under five minutes; the
  // default gives early launches an hour.
  const formTimeoutMs = Number(env.CIRCLE_FORM_TIMEOUT_MIN ?? 60) * 60 * 1000;
  const demo = env.DEMO_MODE === "true";
  return createApp({
    db,
    sendCode,
    production,
    demo,
    digipay: createDigipay(env),
    opsPhones,
    formTimeoutMs,
    persistentStorage,
  });
}
