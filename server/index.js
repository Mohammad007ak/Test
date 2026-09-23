import express from "express";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createAppFromEnv } from "./config.js";

// A setting that would make the server unsafe or broken stops it here; say
// which one in a single line that's easy to spot in the host's logs.
let app;
try {
  app = await createAppFromEnv();
} catch (error) {
  console.error(`\n❌ Server did not start / سرور بالا نیامد: ${error.message}\n`);
  process.exit(1);
}
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

// The app lives at the root: opened from the Digipay mini-app or by typing
// the bare domain. Old /app/ links still work and move to the root. The
// marketing page is at /welcome/.
const sendApp = (req, res) => res.sendFile("app/index.html", { root: dist });
app.get("/", sendApp);
app.get(["/app", "/app/{*path}"], (req, res) => {
  const query = req.originalUrl.includes("?") ? req.originalUrl.slice(req.originalUrl.indexOf("?")) : "";
  res.redirect(301, `/${query}`);
});
// Read from disk rather than sendFile: a failed sendFile answers a bare
// "Not Found" without saying why, and this page must not silently vanish.
function sendPage(file) {
  return (req, res) => {
    try {
      res
        .type("html")
        .set("Cache-Control", "no-cache")
        .send(readFileSync(`${dist}/${file}`, "utf8"));
    } catch (error) {
      console.error(`Could not serve ${req.originalUrl} from ${dist}/${file}: ${error.message}`);
      res.status(500).type("text").send("این صفحه موقتاً در دسترس نیست.");
    }
  };
}
app.get(["/welcome", "/welcome/"], sendPage("index.html"));

// The terms page names how to reach the business. The details come from
// the environment (CONTACT_*), so they can change without a rebuild.
const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
function contactHtml(env = process.env) {
  const rows = [
    ["نام کسب‌وکار", env.CONTACT_COMPANY],
    [
      "ایمیل پشتیبانی",
      env.CONTACT_EMAIL &&
        `<a href="mailto:${escapeHtml(env.CONTACT_EMAIL)}" dir="ltr">${escapeHtml(env.CONTACT_EMAIL)}</a>`,
    ],
    [
      "تلفن پشتیبانی",
      env.CONTACT_PHONE &&
        `<a href="tel:${escapeHtml(env.CONTACT_PHONE)}" dir="ltr">${escapeHtml(env.CONTACT_PHONE)}</a>`,
    ],
    ["نشانی", env.CONTACT_ADDRESS],
  ].filter(([, v]) => v);
  if (!rows.length) return "";
  const items = rows
    .map(([k, v]) => `<li><b>${k}:</b> ${k.startsWith("ایمیل") || k.startsWith("تلفن") ? v : escapeHtml(v)}</li>`)
    .join("\n            ");
  return `<h2 id="contact">تماس با ما</h2>\n          <ul>\n            ${items}\n          </ul>`;
}
let termsPage = null;
app.get(["/terms", "/terms/"], (req, res) => {
  termsPage ??= readFileSync(`${dist}/terms/index.html`, "utf8");
  res.type("html").send(termsPage.replace("<!--contact-->", contactHtml()));
});

// Hashed build assets never change, so browsers may keep them for a year.
app.use("/assets", express.static(`${dist}/assets`, { immutable: true, maxAge: "1y" }));
app.use(express.static(dist, { maxAge: "1h" }));

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
