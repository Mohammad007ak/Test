/* Service Worker «وزیر»: اپ نصب‌شده سریع باز شود و بی‌اینترنت هم صفحه آخر یا صفحه آفلاین را نشان دهد.
   - فایل‌های استاتیک (CSS/JS/فونت/آیکون، با نشانه نسخه در آدرس): اول از کش.
   - صفحه‌ها: اول از شبکه؛ اگر شبکه نبود، آخرین نسخه همان صفحه یا صفحه آفلاین.
   - درخواست‌های غیر GET، /api و چت هرگز کش نمی‌شوند.
   کش صفحه‌ها با خروج از حساب پاک می‌شود (app.js در صفحه ورود). */
const VERSION = "v1";
const STATIC = "vazir-static-" + VERSION;
const PAGES = "vazir-pages";
const OFFLINE = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(STATIC).then((c) => c.add(OFFLINE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("vazir-static-") && k !== STATIC).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "clear-pages") event.waitUntil(caches.delete(PAGES));
});

async function trim(name, max) {
  const cache = await caches.open(name);
  const keys = await cache.keys();
  for (let i = 0; i < keys.length - max; i++) await cache.delete(keys[i]);
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/assistant/") || url.pathname === "/sw.js") return;
  // ویدئو تکه‌تکه (Range) می‌آید؛ کش آن در Safari آیفون پخش را خراب می‌کند
  if (req.headers.has("range") || url.pathname.includes("/video/")) return;

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(STATIC).then((c) => c.put(req, copy)).then(() => trim(STATIC, 80));
        }
        return res;
      }))
    );
    return;
  }

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).then((res) => {
        const html = (res.headers.get("content-type") || "").includes("text/html");
        if (res.ok && !res.redirected && html) {
          const copy = res.clone();
          caches.open(PAGES).then((c) => c.put(req, copy)).then(() => trim(PAGES, 30));
        }
        return res;
      }).catch(() => caches.match(req, { cacheName: PAGES }).then((hit) => hit || caches.match(OFFLINE)))
    );
  }
});
