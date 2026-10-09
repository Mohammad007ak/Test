// رندر کاروسل: node store/social/render_carousel.js <نام بدون .html> <پیشوند خروجی>
// مثال: node store/social/render_carousel.js carousel-loan-gold loan-gold ← store/social/loan-gold-1..5.png
const { chromium } = require(process.env.PLAYWRIGHT || "playwright");
const path = require("path");
const [name, prefix] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  for (let s = 1; s <= 5; s++) {
    await page.goto(`file://${path.join(__dirname, name + ".html")}?s=${s}`);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(__dirname, `${prefix}-${s}.png`) });
  }
  await browser.close();
})();
