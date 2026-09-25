// Builds promo.html: a 60-second, 9:16 motion-graphics promo for Digi Gharz.
// Every motion is a CSS animation on one absolute timeline, so the page can
// be "seeked" to any instant (window.seek(t)) and captured frame by frame.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// The app's own coin character (src/ui/Figure.jsx), minus its React wrapper.
const figureSource = readFileSync(new URL("../src/ui/Figure.jsx", import.meta.url), "utf8");
const { figureSvg } = await import(
  "data:text/javascript," +
    encodeURIComponent(
      figureSource.slice(figureSource.indexOf("export const INK"), figureSource.indexOf("export function Figure(")),
    )
);

const FONTS = fileURLToPath(new URL("../node_modules/@fontsource-variable", import.meta.url));
const fig = (opts = {}, pose = "stand") => figureSvg(pose, opts);
const F = (h, opts, pose, cls = "") => `<span class="fig ${cls}" style="height:${h}px">${fig(opts, pose)}</span>`;
// A walking figure: the two steps alternate.
const W = (h, opts = {}) =>
  `<span class="walker" style="height:${h}px">${F(h, opts, "a", "wa")}${F(h, opts, "b", "wb")}</span>`;
const fa = (n) => String(n).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[d]);

// Scenes: [start, end] in seconds.
const S = {
  bank: [0, 7.5],
  family: [7.5, 13.5],
  reveal: [13.5, 19],
  group: [19, 26],
  pot: [26, 33],
  draw: [33, 41.5],
  guarantee: [41.5, 48.5],
  free: [48.5, 53.5],
  cta: [53.5, 60],
};
export const DURATION = 60;

const scene = (name, bg, body) => {
  const [s, e] = S[name];
  return `<section class="sc ${name}" style="--s:${s}s;background:${bg};animation:sc-vis ${e - s}s linear ${s}s both">${body}</section>`;
};
// A caption sticker that pops in at `at` seconds into its scene.
const cap = (text, at, until = null, cls = "") =>
  `<div class="cap ${cls}" style="--a:${at}s;${until ? `--u:${until}s;` : ""}">${text}</div>`;

const confetti = (n, at, cx = 50, cy = 45) =>
  Array.from({ length: n }, (_, i) => {
    const a = (Math.PI * 2 * i) / n + (i % 3) * 0.2;
    const d = 140 + ((i * 37) % 160);
    const colors = ["#ffc53d", "#ffffff", "#3ddc84", "#ff6b6b", "#8fd0ff"];
    return `<i class="cf" style="left:${cx}%;top:${cy}%;--x:${Math.cos(a) * d}px;--y:${Math.sin(a) * d - 60}px;--r:${((i * 97) % 720) - 360}deg;background:${colors[i % 5]};--a:${at + (i % 5) * 0.03}s"></i>`;
  }).join("");

// ---------- 1. the bank: guarantor? collateral? months of waiting ----------
const bank = scene(
  "bank",
  "#0000ff",
  `
  <svg class="bank-bldg" viewBox="0 0 220 230"><g fill="#fff" stroke="#111126" stroke-width="6" stroke-linejoin="round">
    <path d="M10 70 L110 12 L210 70 Z"/><rect x="18" y="70" width="184" height="18"/>
    <rect x="34" y="96" width="22" height="100"/><rect x="82" y="96" width="22" height="100"/><rect x="130" y="96" width="22" height="100"/><rect x="170" y="96" width="22" height="100"/>
    <rect x="10" y="196" width="200" height="22"/></g>
    <text x="110" y="62" text-anchor="middle" font-size="26" font-weight="900" fill="#111126">بانک</text></svg>
  <span class="stamp s1" style="--a:1.9s">ضامن؟</span>
  <span class="stamp s2" style="--a:2.6s">وثیقه؟</span>
  <span class="stamp s3" style="--a:3.3s">۳ ماه صبر!</span>
  <div class="bank-me">
    <span class="walk-in">${W(210)}</span>
    <span class="sad">${F(210, { angry: true })}</span>
  </div>
  ${cap("وام لازم داری؟", 0.3, 2.9)}
  ${cap("بانک: ضامن، وثیقه و ماه‌ها انتظار…", 3.1, null, "late")}
`,
);

// ---------- 2. the family fund notebook: pages everywhere, arguing ----------
const pages = Array.from(
  { length: 9 },
  (_, i) =>
    `<i class="page" style="--a:${0.8 + i * 0.25}s;--x:${(i % 3) * 140 - 140}px;--y:${-260 - (i % 4) * 60}px;--r:${((i * 83) % 360) - 180}deg"></i>`,
).join("");
const family = scene(
  "family",
  "#ffc53d",
  `
  <svg class="book" viewBox="0 0 200 140"><g stroke="#111126" stroke-width="6" stroke-linejoin="round">
    <path d="M100 20 C70 8 30 8 10 16 V128 C30 120 70 120 100 132 Z" fill="#fff"/>
    <path d="M100 20 C130 8 170 8 190 16 V128 C170 120 130 120 100 132 Z" fill="#fff"/>
    <path d="M30 40 H80 M30 60 H80 M30 80 H70 M120 40 H170 M120 60 H170 M120 80 H160" stroke-width="4"/></g></svg>
  ${pages}
  <div class="fam-argue">
    <span class="shake" style="--d:0s">${F(170, { angry: true })}</span>
    <span class="q q1">؟</span><span class="q q2">!؟</span><span class="q q3">؟</span>
    <span class="shake" style="--d:0.05s">${F(170, { angry: true }, "a")}</span>
    <span class="shake" style="--d:0.1s">${F(170, { angry: true }, "b")}</span>
  </div>
  ${cap("صندوق فامیلی؟ دفترچه، حساب‌وکتاب و دعوا سر نوبت!", 0.4, null, "dark")}
`,
);

// ---------- 3. Digi Gharz arrives ----------
const rain = Array.from(
  { length: 16 },
  (_, i) =>
    `<i class="coin rain" style="left:${(i * 29) % 100}%;--a:${(i * 0.19) % 2.4}s;width:${22 + ((i * 7) % 18)}px;height:${22 + ((i * 7) % 18)}px"></i>`,
).join("");
const reveal = scene(
  "reveal",
  "#0000ff",
  `
  ${rain}
  <div class="hero-dg"><span class="drop"><span class="squash">${F(330, { logo: true })}</span></span></div>
  <h1 class="brand" style="--a:1.3s">دیجی قرض</h1>
  <p class="tagline" style="--a:1.8s">وام گروهی تضمینی، داخل دیجی‌پی</p>
`,
);

// ---------- 4. a group of twelve ----------
const twelve = Array.from(
  { length: 12 },
  (_, i) =>
    `<span class="drop-sm" style="--a:${0.3 + i * 0.16}s"><span class="wave" style="--w:${2.8 + (i % 4) * 0.09 + Math.floor(i / 4) * 0.25}s">${F(118, { logo: i === 0 })}</span></span>`,
).join("");
const group = scene(
  "group",
  "#0000ff",
  `
  <div class="grid12">${twelve}</div>
  <div class="count-pill"><b data-count="12" data-from="0.3" data-to="2.3" data-scene="group"></b> نفر</div>
  ${cap("۱۲ نفر یک گروه می‌شوند؛ هر ماه هر نفر ۵ میلیون می‌گذارد", 0.4)}
`,
);

// ---------- 5. every share into the pot, all of it to one person ----------
const givers = Array.from({ length: 6 }, (_, i) => {
  const dx = (2.5 - i) * 76;
  return `<span class="giver">${F(96, {}, i % 2 ? "a" : "stand")}
    <span class="cx" style="--a:${0.5 + i * 0.28}s;--dx:${dx}px"><span class="cy" style="--a:${0.5 + i * 0.28}s"><i class="coin spin"></i></span></span></span>`;
}).join("");
const pot = scene(
  "pot",
  "#0000ff",
  `
  <div class="givers">${givers}</div>
  <div class="potbox"><i class="coin big spin"></i><b data-count="60" data-from="0.9" data-to="2.7" data-scene="pot"></b><span>میلیون</span></div>
  <div class="winner-walk">${W(150, { face: "#ffc53d" })}</div>
  ${confetti(26, 3.3, 50, 58)}
  ${cap("هر ماه کل مبلغ، ۶۰ میلیون تومان، یک‌جا به یک نفر می‌رسد", 0.3)}
`,
);

// ---------- 6. the provably fair draw ----------
const seats = 10;
const ring = Array.from({ length: seats }, (_, i) => {
  const a = (i / seats) * 2 * Math.PI - Math.PI / 2;
  return `<span class="seat" data-seat="${i}" style="left:${50 + Math.cos(a) * 40}%;top:${50 + Math.sin(a) * 40}%">
    <i class="glow"></i><span class="nerv" style="--d:${i * -0.03}s">${F(100, {})}</span>
    ${i === 7 ? `<span class="won">${F(100, { check: true, face: "#ffc53d" })}</span>` : ""}</span>`;
}).join("");
const draw = scene(
  "draw",
  "#0000ff",
  `
  <div class="ring">${ring}<span class="lock"><svg viewBox="0 0 24 24" width="46" height="46" fill="none" stroke="#111126" stroke-width="2.4" stroke-linecap="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg></span></div>
  <b class="drum">دررررر…</b>
  ${confetti(34, 4.9, 50, 44)}
  ${cap("قرعه‌ی قابل اثبات: نتیجه از قبل قفل است و هر کس خودش بررسی می‌کند", 0.3)}
`,
);

// ---------- 7. the Digipay guarantee ----------
const guarantee = scene(
  "guarantee",
  "#0000ff",
  `
  <div class="gu-late"><span class="calm">${F(230, {})}</span><span class="mad"><span class="fume">${F(230, { angry: true })}</span><i class="steam t1"></i><i class="steam t2"></i><i class="steam t3"></i></span></div>
  <div class="gu-dg"><span class="swoop">${F(230, { logo: true }, "a")}</span><span class="shield"><svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="#111126" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg></span></div>
  ${cap("قسطی جا ماند؟ دیجی‌پی ضمانت می‌کند؛ مبلغ برنده همیشه کامل است", 0.3)}
`,
);

// ---------- 8. the family fund, free ----------
const free = scene(
  "free",
  "#0000ff",
  `
  <svg class="roof" viewBox="0 0 400 130"><path d="M24 124 L200 16 L376 124"/></svg>
  <div class="fam-line">${["stand", "a", "stand", "b"].map((p, i) => `<span class="hop" style="--a:${0.2 + i * 0.22}s">${F(i === 1 ? 190 : 160, { face: i === 1 ? "#ffc53d" : "#fff" }, p)}</span>`).join("")}</div>
  <span class="free-tag" style="--a:1.8s">رایگان!</span>
  ${cap("صندوق خانوادگی‌ات را هم رایگان و بدون دفترچه مدیریت کن", 0.3)}
`,
);

// ---------- 9. call to action ----------
const cheer = Array.from(
  { length: 7 },
  (_, i) =>
    `<span class="${i === 3 ? "flip" : "cheer"}" style="--d:${i * 0.1}s">${F(i === 3 ? 230 : 140, { logo: i === 3 }, i % 2 ? "a" : "b")}</span>`,
).join("");
const cta = scene(
  "cta",
  "#0000ff",
  `
  ${confetti(40, 0.2, 50, 60)}
  <h1 class="brand end" style="--a:0.2s">دیجی قرض</h1>
  <p class="tagline end" style="--a:0.6s">با هم، زودتر به پول برسید</p>
  <div class="crowd-end">${cheer}</div>
  <div class="cta-pill" style="--a:1.2s">همین حالا در اپ دیجی‌پی</div>
  <div class="cta-url" style="--a:1.6s">digigharz.darkube.ir</div>
`,
);

const html = `<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>Digi Gharz promo</title>
<style>
@font-face{font-family:Estedad;src:url(file://${FONTS}/estedad/files/estedad-arabic-wght-normal.woff2) format("woff2");font-weight:100 900}
@font-face{font-family:Vazirmatn;src:url(file://${FONTS}/vazirmatn/files/vazirmatn-arabic-wght-normal.woff2) format("woff2");font-weight:100 900}
*{box-sizing:border-box;margin:0}
html,body{width:540px;height:960px;overflow:hidden;background:#0000ff}
body{font-family:Estedad,Vazirmatn,sans-serif;color:#fff}
#stage{position:relative;width:540px;height:960px;overflow:hidden}
.sc{position:absolute;inset:0;overflow:hidden}
@keyframes sc-vis{0%{opacity:0}4%{opacity:1}96%{opacity:1}100%{opacity:0}}
.fig{display:inline-block;line-height:0}.fig svg{height:100%;width:auto;overflow:visible}
.walker{position:relative;display:inline-block;line-height:0}
.walker .wb{position:absolute;inset:0 auto auto 0}
.walker .wa{animation:stA .36s steps(1) infinite}.walker .wb{animation:stB .36s steps(1) infinite}
@keyframes stA{50%{opacity:0}}@keyframes stB{0%{opacity:0}50%{opacity:1}}
/* captions */
.cap{position:absolute;left:28px;right:28px;bottom:74px;padding:18px 22px;border:4px solid #111126;border-radius:26px;background:#fff;color:#111126;font-size:31px;font-weight:900;line-height:1.55;text-align:center;box-shadow:0 7px 0 #111126;
  animation:cap-in .5s cubic-bezier(.34,1.56,.64,1) calc(var(--s) + var(--a)) both}
.cap[style*="--u"]{animation:cap-in .5s cubic-bezier(.34,1.56,.64,1) calc(var(--s) + var(--a)) both, cap-out .25s ease-in calc(var(--s) + var(--u)) both}
.cap.dark{background:#111126;color:#fff;box-shadow:0 7px 0 #0000ff}
@keyframes cap-in{from{opacity:0;transform:translateY(60px) scale(.7)}}
@keyframes cap-out{to{opacity:0;transform:scale(.8)}}
/* shared */
.coin{display:block;width:36px;height:36px;border:4px solid #111126;border-radius:50%;background:#ffc53d;box-shadow:inset -6px 0 0 #e09a00}
.spin{animation:spin .5s linear infinite}@keyframes spin{50%{transform:scaleX(.15)}}
.cf{position:absolute;width:14px;height:22px;border-radius:4px;border:2px solid #111126;opacity:0;animation:cf 1.8s cubic-bezier(.2,.8,.3,1) calc(var(--s) + var(--a)) both}
@keyframes cf{0%{opacity:1;transform:translate(-50%,-50%) rotate(0)}80%{opacity:1}100%{opacity:0;transform:translate(calc(-50% + var(--x)),calc(-50% + var(--y) + 260px)) rotate(var(--r))}}
@keyframes pop{from{opacity:0;transform:scale(.2)}}
@keyframes squash{0%{transform:scale(1.28,.7)}40%{transform:scale(.9,1.12)}70%{transform:scale(1.04,.97)}100%{transform:none}}
/* 1 bank */
.bank-bldg{position:absolute;right:22px;top:170px;width:260px;animation:pop .6s cubic-bezier(.34,1.56,.64,1) calc(var(--s) + .2s) both}
.stamp{position:absolute;padding:8px 18px;border:4px solid #111126;border-radius:14px;background:#ff5a5f;color:#fff;font-size:30px;font-weight:900;box-shadow:0 5px 0 #111126;animation:stamp .45s cubic-bezier(.34,1.56,.64,1) calc(var(--s) + var(--a)) both}
.stamp.s1{right:170px;top:130px;transform:rotate(-8deg)}.stamp.s2{right:40px;top:300px;transform:rotate(7deg)}.stamp.s3{right:120px;top:440px;transform:rotate(-4deg)}
@keyframes stamp{from{opacity:0;scale:2.4}}
.bank-me{position:absolute;left:40px;top:380px;height:210px}
.walk-in{position:absolute;left:0;top:0;animation:walk-in 1.6s linear calc(var(--s) + 0s) both, fade-out .01s linear calc(var(--s) + 4s) both}
@keyframes walk-in{from{transform:translateX(-360px)}}
@keyframes fade-out{to{opacity:0}}
.sad{position:absolute;left:0;top:0;opacity:0;animation:appear .01s linear calc(var(--s) + 4s) both, shake .14s linear calc(var(--s) + 4s) infinite}
@keyframes appear{to{opacity:1}}
@keyframes shake{25%{transform:translateX(-4px) rotate(-2deg)}75%{transform:translateX(4px) rotate(2deg)}}
/* 2 family */
.book{position:absolute;left:50%;top:170px;width:300px;margin-left:-150px;animation:book .3s ease-in-out calc(var(--s) + .6s) 10 alternate}
@keyframes book{to{transform:rotate(-5deg) scale(1.05)}}
.page{position:absolute;left:50%;top:260px;width:70px;height:90px;margin-left:-35px;border:4px solid #111126;border-radius:6px;background:#fff;opacity:0;animation:page 1.4s ease-out calc(var(--s) + var(--a)) both}
@keyframes page{0%{opacity:1;transform:translate(0,0) rotate(0)}100%{opacity:0;transform:translate(var(--x),var(--y)) rotate(var(--r))}}
.fam-argue{position:absolute;left:0;right:0;top:390px;display:flex;justify-content:center;gap:10px}
.shake{display:inline-block;animation:shake .14s linear calc(var(--s) + var(--d)) infinite}
.q{position:absolute;font-size:64px;font-weight:900;color:#111126;animation:pop .4s cubic-bezier(.34,1.56,.64,1) both}
.q1{left:90px;top:-40px;animation-delay:calc(var(--s) + 1s)}.q2{left:250px;top:-70px;animation-delay:calc(var(--s) + 1.5s)}.q3{right:80px;top:-30px;animation-delay:calc(var(--s) + 2s)}
/* 3 reveal */
.rain{position:absolute;top:-60px;animation:rain 2.4s linear calc(var(--s) + var(--a)) infinite, spin .6s linear infinite}
@keyframes rain{to{top:110%}}
.hero-dg{position:absolute;left:0;right:0;top:230px;text-align:center}
.drop{display:inline-block;animation:drop .7s cubic-bezier(.5,0,.9,.6) calc(var(--s) + .1s) both}
@keyframes drop{from{transform:translateY(-700px)}}
.squash{display:inline-block;transform-origin:bottom center;animation:squash .6s ease-out calc(var(--s) + .8s) both}
.brand{position:absolute;left:0;right:0;top:92px;text-align:center;font-size:84px;font-weight:900;color:#fff;-webkit-text-stroke:3px #111126;text-shadow:0 7px 0 #111126;animation:pop .6s cubic-bezier(.34,1.56,.64,1) calc(var(--s) + var(--a)) both}
.tagline{position:absolute;left:30px;right:30px;top:640px;padding:14px;border:4px solid #111126;border-radius:20px;background:#ffc53d;color:#111126;text-align:center;font-size:32px;font-weight:900;box-shadow:0 6px 0 #111126;animation:pop .5s cubic-bezier(.34,1.56,.64,1) calc(var(--s) + var(--a)) both}
/* 4 group */
.grid12{position:absolute;left:0;right:0;top:120px;display:grid;grid-template-columns:repeat(4,auto);justify-content:center;gap:14px 22px}
.drop-sm{display:inline-block;animation:drop .5s cubic-bezier(.5,0,.9,.6) calc(var(--s) + var(--a)) both}
.wave{display:inline-block;transform-origin:bottom center;animation:wave 2.2s ease-in-out calc(var(--s) + var(--w)) infinite}
@keyframes wave{0%,14%,100%{transform:none}6%{transform:translateY(-30px) scale(1.05,.95)}}
.count-pill{position:absolute;left:50%;top:40px;transform:translateX(-50%);padding:6px 26px;border:4px solid #111126;border-radius:999px;background:#ffc53d;color:#111126;font-size:40px;font-weight:900;white-space:nowrap}
/* 5 pot */
.givers{position:absolute;left:0;right:0;top:120px;display:flex;justify-content:center;gap:4px}
.giver{position:relative}
.cx{position:absolute;left:50%;top:10px;margin-left:-18px;opacity:0;animation:cx 1s linear calc(var(--s) + var(--a)) both}
.cy{display:block;animation:cy 1s linear calc(var(--s) + var(--a)) both}
@keyframes cx{0%{opacity:1;transform:translateX(0)}95%{opacity:1}100%{opacity:0;transform:translateX(var(--dx))}}
@keyframes cy{0%{transform:translateY(0);animation-timing-function:ease-out}35%{transform:translateY(-90px);animation-timing-function:ease-in}100%{transform:translateY(250px)}}
.potbox{position:absolute;left:50%;top:400px;transform:translateX(-50%);display:flex;align-items:center;gap:14px;padding:14px 30px;border:4px solid #111126;border-radius:999px;background:#fff;color:#111126;font-size:46px;font-weight:900;white-space:nowrap;box-shadow:0 7px 0 #111126;animation:jig .22s ease-in-out calc(var(--s) + .9s) 9, potfull .5s cubic-bezier(.34,1.56,.64,1) calc(var(--s) + 3.2s) both}
.potbox .coin.big{width:56px;height:56px}
@keyframes jig{25%{rotate:-4deg;scale:1.05}75%{rotate:4deg;scale:1.05}}
@keyframes potfull{to{background:#ffc53d}}
.winner-walk{position:absolute;left:0;top:560px;animation:winwalk 2s ease-out calc(var(--s) + 3.4s) both}
@keyframes winwalk{from{transform:translateX(-200px)}to{transform:translateX(190px)}}
/* 6 draw */
.ring{position:absolute;left:50%;top:70px;width:500px;height:520px;margin-left:-250px}
.seat{position:absolute;transform:translate(-50%,-62%);line-height:0}
.glow{position:absolute;left:50%;top:-4px;width:120px;height:120px;margin-left:-60px;border-radius:50%;background:radial-gradient(circle,#ffc53d 0 36%,rgb(255 197 61/0) 70%);opacity:0}
.nerv{display:inline-block;animation:shake .16s linear calc(var(--s) + var(--d)) 28}
.won{position:absolute;left:0;bottom:0;opacity:0;line-height:0;animation:appear .01s linear calc(var(--s) + 4.8s) both, jump .5s ease-in-out calc(var(--s) + 4.8s) infinite alternate}
.seat[data-seat="7"] .nerv{animation:shake .16s linear calc(var(--s) + 0s) 28, fade-out .01s linear calc(var(--s) + 4.8s) both}
@keyframes jump{from{transform:translateY(0) scale(1.08,.92)}to{transform:translateY(-34px) scale(.96,1.06)}}
.lock{position:absolute;left:50%;top:50%;display:grid;place-items:center;width:104px;height:104px;margin:-52px 0 0 -52px;border:4px solid #111126;border-radius:50%;background:#fff;animation:jig .25s ease-in-out calc(var(--s) + .4s) 18}
.drum{position:absolute;left:0;right:0;top:600px;text-align:center;color:#ffc53d;font-size:40px;font-weight:900;animation:shake .2s linear calc(var(--s) + .3s) 22, fade-out .2s linear calc(var(--s) + 4.6s) both}
/* 7 guarantee */
.guarantee{animation:sc-vis 7s linear calc(var(--s)) both, redflash 3.2s ease-in-out calc(var(--s) + .6s) both !important}
@keyframes redflash{0%{background:#0000ff}8%,68%{background:#e0242f}76%,100%{background:#0000ff}}
.gu-late{position:absolute;right:40px;top:300px;line-height:0}
.calm{display:block;animation:fade-out .01s linear calc(var(--s) + 1s) both}
.mad{position:absolute;inset:0;opacity:0;animation:appear .01s linear calc(var(--s) + 1s) both}
.fume{display:block;animation:shake .12s linear calc(var(--s) + 1s) infinite}
.steam{position:absolute;top:10px;width:28px;height:28px;border:4px solid #111126;border-radius:50%;background:#fff;opacity:0;animation:steam 1.2s ease-out calc(var(--s) + 1.2s) infinite}
.steam.t1{left:20%}.steam.t2{left:50%;animation-delay:calc(var(--s) + 1.6s)}.steam.t3{left:75%;animation-delay:calc(var(--s) + 2s)}
@keyframes steam{0%{opacity:.9;transform:translateY(0) scale(.5)}100%{opacity:0;transform:translateY(-110px) scale(1.5)}}
.gu-dg{position:absolute;left:40px;top:300px;line-height:0}
.swoop{display:inline-block;animation:swoop .9s cubic-bezier(.3,.8,.4,1) calc(var(--s) + 2s) both}
@keyframes swoop{from{opacity:0;transform:translate(-420px,-420px) rotate(-60deg)}to{opacity:1;transform:none}}
.shield{position:absolute;top:-14px;right:-18px;display:grid;place-items:center;width:84px;height:84px;border:4px solid #111126;border-radius:50%;background:#3ddc84;animation:pop .4s cubic-bezier(.34,1.56,.64,1) calc(var(--s) + 2.9s) both, pulse 1.1s ease-out calc(var(--s) + 3.3s) infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgb(61 220 132/.7)}100%{box-shadow:0 0 0 30px rgb(61 220 132/0)}}
/* 8 free */
.roof{position:absolute;left:50%;top:130px;width:460px;margin-left:-230px;overflow:visible}
.roof path{fill:none;stroke:#fff;stroke-width:14;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:520;stroke-dashoffset:520;animation:roof 1s ease-out calc(var(--s) + 1.2s) forwards}
@keyframes roof{to{stroke-dashoffset:0}}
.fam-line{position:absolute;left:0;right:0;top:300px;display:flex;justify-content:center;align-items:flex-end}
.hop{display:inline-block;transform-origin:bottom center;animation:hop .7s ease-out calc(var(--s) + var(--a)) both}
@keyframes hop{0%{opacity:0;transform:translate(120px,0)}30%{opacity:1;transform:translate(80px,-60px)}60%{transform:translate(30px,0) scale(1.1,.9)}80%{transform:translate(10px,-20px)}100%{transform:none}}
.free-tag{position:absolute;left:50%;top:560px;transform:translateX(-50%);padding:8px 34px;border:4px solid #111126;border-radius:999px;background:#ffc53d;color:#111126;font-size:46px;font-weight:900;box-shadow:0 6px 0 #111126;animation:pop .45s cubic-bezier(.34,1.56,.64,1) calc(var(--s) + var(--a)) both, wob 1.2s ease-in-out calc(var(--s) + 2.3s) infinite}
@keyframes wob{25%{rotate:-6deg}75%{rotate:6deg}}
/* 9 cta */
.brand.end{top:120px}
.tagline.end{top:250px;background:#fff}
.crowd-end{position:absolute;left:0;right:0;bottom:200px;display:flex;justify-content:center;align-items:flex-end}
.cheer,.flip{display:block;margin-inline:-10px;transform-origin:center 70%}
.cheer{animation:cheer .55s ease-in-out calc(var(--s) + var(--d)) infinite alternate}
@keyframes cheer{from{transform:scale(1.05,.95)}to{transform:translateY(-30px) scale(.97,1.04)}}
.flip{animation:flip 1.6s ease-in-out calc(var(--s) + .6s) infinite}
@keyframes flip{0%,40%,100%{transform:none}55%{transform:translateY(-120px) rotate(-180deg)}70%{transform:translateY(-120px) rotate(-360deg)}85%{transform:rotate(-360deg) scale(1.1,.9)}}
.cta-url{position:absolute;left:0;right:0;bottom:26px;text-align:center;font-family:sans-serif;font-size:24px;font-weight:700;color:#fff;letter-spacing:.5px;animation:pop .5s ease-out calc(var(--s) + var(--a)) both}
.cta-pill{position:absolute;left:36px;right:36px;bottom:84px;padding:18px;border:4px solid #111126;border-radius:999px;background:#ffc53d;color:#111126;text-align:center;font-size:36px;font-weight:900;box-shadow:0 7px 0 #111126;animation:pop .5s cubic-bezier(.34,1.56,.64,1) calc(var(--s) + var(--a)) both, wob 1.4s ease-in-out calc(var(--s) + 2s) infinite}
</style></head><body><div id="stage">
${bank}${family}${reveal}${group}${pot}${draw}${guarantee}${free}${cta}
</div>
<script>
const fa = (n) => String(n).replace(/\\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[d]);
const START = ${JSON.stringify(Object.fromEntries(Object.entries(S).map(([k, v]) => [k, v[0]])))};
const ease = (k) => 1 - (1 - k) ** 3;
// The draw: the light hops round the ring, slowing down, onto seat 7.
const hops = (() => { const out = []; let t = 0.5; const steps = 2 * ${seats} + 7;
  for (let i = 0; i <= steps; i++) { out.push([t, i % ${seats}]); t += 0.06 + 0.3 * (i / steps) ** 3; } return out; })();
window.seek = (t) => {
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
  for (const el of document.querySelectorAll("[data-count]")) {
    const s = START[el.dataset.scene], from = +el.dataset.from, to = +el.dataset.to;
    const k = Math.min(1, Math.max(0, (t - s - from) / (to - from)));
    el.textContent = fa(Math.round(+el.dataset.count * ease(k)));
  }
  const local = t - START.draw;
  let lit = -1; for (const [at, i] of hops) if (local >= at) lit = i;
  document.querySelectorAll(".seat").forEach((s) => (s.querySelector(".glow").style.opacity = +s.dataset.seat === lit && local < 8 ? 0.95 : 0));
};
window.seek(0);
</script></body></html>`;

writeFileSync(new URL("./promo.html", import.meta.url), html);
console.log("built promo.html,", DURATION, "s");
