// عکس استوری قیمت امروز: node store/social/render_story.js ← store/social/story-prices.png
const { chromium } = require(process.env.PLAYWRIGHT || "playwright");
const path = require("path");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto("file://" + path.join(__dirname, "story-prices.html"));
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(__dirname, "story-prices.png") });
  await browser.close();
})();
