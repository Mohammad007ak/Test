// Captures promo.html frame by frame (window.seek) and encodes it, with
// music.wav, into digigharz-promo.mp4 (1080×1920, 30 fps, 60 s).
// `--wide` renders promo-wide.html into digigharz-promo-wide.mp4 (1920×1080).
import { chromium } from "playwright";
import { spawn } from "node:child_process";
const D = new URL("./", import.meta.url).pathname;
const FFMPEG = process.env.FFMPEG ?? "ffmpeg";
const WIDE = process.argv.includes("--wide");
const [W, H] = WIDE ? [960, 540] : [540, 960];
const FPS = 30,
  DUR = 60;
const ff = spawn(
  FFMPEG,
  [
    "-y",
    "-loglevel",
    "error",
    "-f",
    "image2pipe",
    "-framerate",
    String(FPS),
    "-i",
    "-",
    "-i",
    D + "music.wav",
    "-c:v",
    "libx264",
    "-preset",
    "medium",
    "-crf",
    "20",
    "-pix_fmt",
    "yuv420p",
    "-profile:v",
    "high",
    "-c:a",
    "aac",
    "-b:a",
    "160k",
    "-movflags",
    "+faststart",
    "-shortest",
    D + (WIDE ? "digigharz-promo-wide.mp4" : "digigharz-promo.mp4"),
  ],
  { stdio: ["pipe", "inherit", "inherit"] },
);
const b = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
const p = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 2 });
await p.goto("file://" + D + (WIDE ? "promo-wide.html" : "promo.html"));
await p.waitForTimeout(1000);
const total = FPS * DUR;
for (let f = 0; f < total; f++) {
  await p.evaluate((t) => window.seek(t), f / FPS);
  const buf = await p.screenshot({ type: "jpeg", quality: 92 });
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
  if (f % 300 === 0) console.log("frame", f);
}
ff.stdin.end();
await new Promise((r) => ff.on("close", r));
await b.close();
console.log("done");
