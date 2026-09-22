import { openDatabase } from "./db.js";
import { createSmsSender } from "./sms.js";
import { createApp } from "./app.js";

// Shared by the production server and the Vite dev middleware.
export function createAppFromEnv(env = process.env) {
  const production = env.NODE_ENV === "production";
  const db = openDatabase(env.DB_PATH ?? "data/sandogh.db");
  const sendCode = createSmsSender({
    apiKey: env.KAVENEGAR_API_KEY,
    template: env.KAVENEGAR_TEMPLATE ?? "sandogh-login",
  });
  return createApp({ db, sendCode, production });
}
