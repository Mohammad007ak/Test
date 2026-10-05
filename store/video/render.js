// ساخت ویدئو از یک صفحه HTML این پوشه (پیش‌فرض ios-sms-setup): فریم‌به‌فریم عکس و ffmpeg.
// اجرا: node store/video/render.js [نام]  ← store/video/<نام>-1080.mp4
// برای آموزش آیفون نسخه سبک سایت و پوستر هم در app/static/video ساخته می‌شود.
const { chromium } = require(process.env.PLAYWRIGHT || "playwright");
const { spawn } = require("child_process");
const path = require("path");

const FPS = 30;
const here = __dirname;
const root = path.resolve(here, "../..");
const name = process.argv[2] || "ios-sms-setup";
const full = path.join(here, `${name}-1080.mp4`);
const site = path.join(root, "app/static/video/ios-sms-setup.mp4");
const poster = path.join(root, "app/static/video/ios-sms-setup.jpg");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto("file://" + path.join(here, `${name}.html`));
  await page.evaluate(() => document.fonts.ready);
  const duration = await page.evaluate(() => window.DURATION);
  const ffmpeg = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS),
    "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow",
    "-movflags", "+faststart", full], { stdio: ["pipe", "inherit", "inherit"] });
  const frames = Math.round(duration * FPS);
  for (let i = 0; i < frames; i++) {
    await page.evaluate((t) => window.render(t), i / FPS);
    const shot = await page.screenshot({ type: "jpeg", quality: 92 });
    if (!ffmpeg.stdin.write(shot)) await new Promise((r) => ffmpeg.stdin.once("drain", r));
    if (i % 150 === 0) console.log(`frame ${i}/${frames}`);
  }
  ffmpeg.stdin.end();
  await new Promise((r) => ffmpeg.on("close", r));
  if (name !== "ios-sms-setup") { await browser.close(); console.log("done", full); return; }
  await page.evaluate(() => window.render(14.2));
  await page.screenshot({ path: poster, type: "jpeg", quality: 80, clip: { x: 0, y: 0, width: 1080, height: 1920 } });
  await browser.close();
  // نسخه سبک سایت: ۵۴۰×۹۶۰
  await new Promise((r) => spawn("ffmpeg", ["-y", "-loglevel", "error", "-i", full, "-vf", "scale=540:960",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "27", "-preset", "slow", "-an", "-movflags", "+faststart", site],
    { stdio: "inherit" }).on("close", r));
  console.log("done", full, site);
})();
