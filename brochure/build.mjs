// Builds the brochure HTML and renders the PDF with Playwright/Chromium.
//   node build.mjs           -> Bank Tejarat edition (src/content.mjs)
//   node build.mjs --board   -> Digikala Group board edition (src/content-board.mjs)
//   node build.mjs --nonum   -> Bank Tejarat edition without figures (src/nonum.mjs)
//   --html  html only   --png  also write per-page PNG previews
import { readFileSync, writeFileSync, mkdirSync, existsSync, rmSync } from "node:fs";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const BOARD = process.argv.includes("--board");
const NONUM = !BOARD && process.argv.includes("--nonum");
const C = BOARD ? await import("./src/content-board.mjs") : await import("./src/content.mjs");
const { SEGMENTS, products, sections } = C;
const SEG_ORDER = Object.keys(SEGMENTS);
const bySeg = (arr) => [...arr].sort((x, y) => SEG_ORDER.indexOf(x.seg) - SEG_ORDER.indexOf(y.seg));

// ---------------------------------------------------------------- helpers
const iconCache = {};
function icon(name) {
  if (!iconCache[name]) {
    const f = path.join(ROOT, "assets/icons", `${name}.svg`);
    if (!existsSync(f)) throw new Error(`missing icon ${name}`);
    iconCache[name] = readFileSync(f, "utf8")
      .replace(/<!--[\s\S]*?-->/g, "")
      .replace(/<svg[^>]*>/, (tag) => tag.replace(/\s(class|width|height)="[^"]*"/g, "").replace(/stroke-width="[^"]*"/, 'stroke-width="1.5"'))
      .trim();
  }
  return `<span class="ic">${iconCache[name]}</span>`;
}
const img = (f) => `assets/img/${f}`;
const faDigits = (s) => String(s).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[d]);

// soft chevron, echoing the Digipay mark (used as background texture)
function swoosh({ x, y, w, color = "#fff", opacity = 0.06, stroke = 0.22 }) {
  const h = w * 0.62;
  const sw = w * stroke;
  return `<svg class="swoosh" style="left:${x};top:${y};width:${w}mm;height:${h + sw}mm" viewBox="${-sw / 2} ${-sw / 2} ${w + sw} ${h + sw}">
    <path d="M0 ${h} L${w / 2} 0 L${w} ${h}" fill="none" stroke="${color}" stroke-opacity="${opacity}" stroke-width="${sw}" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function segChips(seg, { onlyActive = false } = {}) {
  return `<div class="segs">${Object.entries(SEGMENTS)
    .filter(([k]) => !onlyActive || (seg[k] && seg[k] !== "none"))
    .map(([k, s]) => {
      const v = seg[k] || "none";
      if (v === "none" && onlyActive) return "";
      const cls = v === "full" ? "seg on" : "seg";
      const label = v === "half" ? `${s.fa} <span style="opacity:.7;font-weight:400">(مکمل)</span>` : s.fa;
      return `<span class="${cls}">${icon(s.icon)}${label}</span>`;
    })
    .join("")}</div>`;
}

// ---------------------------------------------------------------- page registry
const pages = []; // {html, toc?: {label, level}}
let productNo = 0;
const productPage = {}; // key -> page index (1-based) for matrix/toc

function add(render, toc) {
  pages.push({ render, toc });
}
const footer = (n, cls = "") => `<div class="footer ${cls}"><span class="num">${n}</span><span class="rule"></span><span class="brand">${C.meta.footer}</span></div>`;

// ---------------------------------------------------------------- page templates
function cover() {
  return `<section class="page navy cover">
    ${swoosh({ x: "-40mm", y: "95mm", w: 200, opacity: 0.07 })}
    ${swoosh({ x: "170mm", y: "-60mm", w: 170, opacity: 0.05 })}
    <div class="inner">
      <img class="logo" src="${img("logo-white.png")}" alt="digipay">
      <h1>${C.meta.title}</h1>
      <div class="sub">${C.meta.subtitle}</div>
      ${BOARD
        ? `<div class="partner"><span>عضو گروه</span><img src="${img("digikala-white.png")}" alt="دیجی‌کالا"></div>`
        : `<div class="partner"><span>قدرت گرفته از</span><img src="${img("tejarat-white.png")}" alt="بانک تجارت"><span class="sep"></span><img src="${img("digikala-white.png")}" alt="دیجی‌کالا"></div>`}
    </div>
    <div class="date">${C.meta.date}</div>
  </section>`;
}

function toc(n) {
  const rows = pages.flatMap((p, i) => (p.toc ? [].concat(p.toc).map((t) => ({ ...t, pg: i + 1 })) : []));
  const half = Math.ceil(rows.length / 2);
  // keep sections together: split at the first section header at/after half
  let cut = rows.findIndex((r, i) => i >= half - 2 && r.level === "sec");
  if (cut < 0) cut = half;
  const col = (rs) =>
    rs
      .map((r) => `<div class="row ${r.level}"><span>${r.label}</span><span class="dots"></span><span class="pg">${r.pg}</span></div>`)
      .join("");
  return `<section class="page navy">
    ${swoosh({ x: "-30mm", y: "120mm", w: 150, opacity: 0.06 })}
    <div class="toc"><h2>فهرست</h2>
      <div class="cols"><div>${col(rows.slice(0, cut))}</div><div>${col(rows.slice(cut))}</div></div>
    </div>${footer(n)}</section>`;
}

function introPage(n) {
  const I = C.intro;
  return `<section class="page">
    ${swoosh({ x: "190mm", y: "110mm", w: 150, color: "#15479e", opacity: 0.04 })}
    <div class="content">
      <div class="h-title">${I.title}</div>
      <p class="lead" style="max-width:190mm">${I.lead}</p>
      <div style="display:grid;grid-template-columns:1.25fr 1fr;gap:12mm;margin-top:9mm">
        <div>
          <div style="font-weight:800;color:var(--navy);font-size:11pt;margin-bottom:3mm">راهنمای استفاده از سند</div>
          <div style="display:grid;gap:3mm">${I.howto
            .map((h, i) => `<div class="idea" style="padding:3.4mm 4mm">${icon(h.icon)}<div><h5>${faDigits(i + 1)}. ${h.t}</h5><p>${h.d}</p></div></div>`)
            .join("")}</div>
        </div>
        <div>
          <div style="font-weight:800;color:var(--navy);font-size:11pt;margin-bottom:3mm">حوزه‌های بانکداری در این سند</div>
          <div style="display:grid;gap:3mm">${Object.values(SEGMENTS)
            .map((s) => `<div class="pill" style="padding:3.6mm 4mm">${icon(s.icon)}<div><b style="color:var(--navy)">${s.fa}</b><div style="font-size:8pt;color:var(--ink-2)">${s.role}</div></div></div>`)
            .join("")}</div>
          <div class="legend" style="margin-top:5mm"><span><i class="seg on" style="padding:.6mm 2.5mm">کاربرد اصلی</i></span><span><i class="seg" style="padding:.6mm 2.5mm">کاربرد مکمل</i></span></div>
        </div>
      </div>
    </div>${footer(n)}</section>`;
}

function divider(n, { title, en, desc, kicker, big, image, related }) {
  if (image) {
    return `<section class="page navy divider" style="display:grid;grid-template-columns:1fr 1fr">
      <div style="position:relative">
        <div class="title-block">${kicker ? `<div class="kicker">${kicker}</div>` : ""}<h2>${title}</h2><div class="ghost">${en.join("<br>")}</div>${desc ? `<p class="desc">${desc}</p>` : ""}</div>
      </div>
      <div style="position:relative;overflow:hidden"><img src="${img(image)}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover" alt=""></div>
      ${footer(n, "")}</section>`;
  }
  return `<section class="page navy divider">
    ${swoosh({ x: "-20mm", y: "105mm", w: 170, opacity: 0.05 })}
    <div class="title-block">${kicker ? `<div class="kicker">${kicker}</div>` : ""}<h2>${title}</h2><div class="ghost">${en.join("<br>")}</div>${desc ? `<p class="desc">${desc}</p>` : ""}
      ${related && related.length ? `<div class="related"><div class="rk">سایر محصولات کاربردی برای این حوزه</div><div class="rl">${related.map((r) => `<span>${r.title}<i>${r.pg}</i></span>`).join("")}</div></div>` : ""}</div>
    ${big ? `<div class="bignum">${big}</div>` : ""}
    ${footer(n)}</section>`;
}

function glancePage(n) {
  const G = C.glance;
  return `<section class="page">
    ${swoosh({ x: "-60mm", y: "40mm", w: 190, color: "#15479e", opacity: 0.035 })}
    <div class="content">
      <div class="h-title">${G.headline}</div>
      <div class="statband" style="margin-top:7mm">${G.stats
        .map((s) => `<div class="s"><span class="n">${s.n}</span><span class="t">${s.t}</span></div>`)
        .join("")}</div>
      <div class="partnerband">
        ${BOARD ? "" : `<div class="p"><img src="${img("tejarat-white.png")}" alt=""><span>قدرت گرفته از بانک تجارت</span></div>`}
        <div class="p"><img src="${img("digikala-white.png")}" alt=""><span>قدرت گرفته از گروه تجارت الکترونیک دیجی‌کالا</span></div>
      </div>
      <div style="display:grid;grid-template-columns:1.35fr 1fr;gap:12mm;margin-top:9mm">
        <div>
          <div class="h-title" style="font-size:13pt">خدمات اصلی دیجی‌پی</div>
          <div class="svc-grid" style="grid-template-columns:repeat(3,1fr);row-gap:3mm">${G.services
            .map((s) => `<div class="svc">${icon(s.icon)}<span>${s.t}</span></div>`)
            .join("")}</div>
        </div>
        <div>
          <div class="h-title" style="font-size:13pt">دنیای کالا و خدمات دیجی‌پی</div>
          <div style="display:flex;gap:6mm;margin-top:4mm;align-items:center">
            <div style="font-family:Outfit;font-weight:600;font-size:34pt;color:var(--navy);line-height:1">15</div>
            <div style="font-size:9pt;font-weight:700;color:var(--navy);line-height:1.6">میلیون تنوع<br>کالا و خدمت</div>
          </div>
          <div class="gcard" style="border:none;padding:0;margin-top:3mm"><div class="tags">${G.categories.map((c) => `<span>${c}</span>`).join("")}</div></div>
        </div>
      </div>
      <div class="timeline">${G.timeline.map((t) => `<div class="tl"><span class="y">${t.y}</span><span class="t en">${t.t}</span></div>`).join("")}</div>
    </div>${footer(n)}</section>`;
}

function networkPage(n) {
  const pts = [
    { icon: "store", t: "خرید آنلاین و حضوری از پذیرندگان در سراسر کشور" },
    { icon: "calendar-clock", t: "پذیرش اعتبار BNPL و خرید اقساطی با وام بانکی" },
    { icon: "qr-code", t: "پرداخت حضوری با دیجی‌کارت، QR Code و صندوق فروشگاهی" },
    { icon: "layers", t: "۱۵ میلیون تنوع کالا و خدمت در ۱۲ گروه اصلی" },
  ];
  return `<section class="page navy" style="display:grid;grid-template-columns:1fr 1fr">
    <div style="position:relative;padding:20mm 18mm 20mm 14mm">
      <div class="h-title">شبکه پذیرندگان دیجی‌پی</div>
      <p class="lead" style="font-size:10pt">حدود ۴۰ هزار نقطه فروش آنلاین و حضوری در سراسر کشور؛ از دیجی‌کالا تا فروشگاه‌های تخصصی در هر شهر. مشتریان دیجی‌پی در همه این پذیرندگان از کیف پول و اعتبار خود استفاده می‌کنند.</p>
      <ul class="feat" style="margin-top:9mm;gap:4.5mm">${pts.map((x) => `<li style="font-size:10pt">${icon(x.icon)}<span>${x.t}</span></li>`).join("")}</ul>
    </div>
    <div style="position:relative;overflow:hidden"><img src="${img("map.jpg")}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover" alt="">
      <div class="statbox" style="top:auto;bottom:26mm"><div class="big">40K</div><div class="lbl">نقطه فروش آنلاین و حضوری در شبکه دیجی‌پی</div></div>
    </div>
    ${footer(n, "half")}</section>`;
}

function merchantsPage(n) {
  const list = JSON.parse(readFileSync(path.join(ROOT, "assets/merchants/merchants.json"), "utf8"));
  return `<section class="page navy">
    ${swoosh({ x: "-30mm", y: "130mm", w: 150, opacity: 0.05 })}
    <div class="content" style="inset:15mm 18mm 20mm">
      <div class="h-title">برخی از پذیرندگان طرف قرارداد دیجی‌پی</div>
      <div class="h-sub">Selected Digipay Merchants</div>
      <div class="mgrid">${list
        .map((m) => `<div class="m"><div class="tile"><img src="assets/merchants/${m.id}.png" alt=""></div><span>${m.fa}</span></div>`)
        .join("")}</div>
    </div>${footer(n)}</section>`;
}

function matrixPage(n) {
  const head = Object.values(SEGMENTS).map((s) => `<th>${icon(s.icon)}${s.fa}</th>`).join("");
  const dot = (v) => `<span class="dot ${v || "none"}"></span>`;
  const body = sections
    .map((sec) => {
      const rows = sec.products
        .map((k) => {
          const p = products[k];
          return `<tr><td class="p">${p.title} <small>${p.matrixSub}</small></td>${Object.keys(SEGMENTS)
            .map((s) => `<td>${dot(p.seg[s])}</td>`)
            .join("")}<td class="pg">${productPage[k] ?? ""}</td></tr>`;
        })
        .join("");
      return `<tr><td class="grp" colspan="${Object.keys(SEGMENTS).length + 2}">${sec.title}</td></tr>${rows}`;
    })
    .join("");
  return `<section class="page">
    <div class="content">
      <div class="h-title">${BOARD ? "نقشه محصولات به تفکیک مشتری" : "نقشه محصولات به تفکیک حوزه بانکداری"}</div>
      <div class="h-sub">${BOARD ? "هر محصول برای کدام گروه از مشتریان دیجی‌پی کاربرد دارد؟" : "هر محصول برای کدام گروه از مشتریان بانک تجارت کاربرد دارد؟"}</div>
      <table class="matrix"><thead><tr><th style="width:36%">محصول / خدمت</th>${head}<th style="width:6%">صفحه</th></tr></thead><tbody>${body}</tbody></table>
      <div class="legend"><span>${dot("full")} کاربرد اصلی</span><span>${dot("half")} کاربرد مکمل</span><span>${dot("none")} —</span></div>
    </div>${footer(n)}</section>`;
}

function welfarePage(n, key) {
  const p = products[key];
  return `<section class="page pale">
    <div class="content">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10mm">
        <div>
          <div class="title-row"><span class="num-badge">${faDigits(p.no)}</span><span class="h-title">${p.title}</span></div>
          <p class="lead" style="max-width:175mm;font-size:9.8pt">${p.lead}</p>
        </div>
        <div style="padding-top:2mm">${segChips(p.seg, { onlyActive: true })}</div>
      </div>
      <div class="trio">${p.trio
        .map(
          (c) => `<div class="card"><img class="img" src="${img(c.img)}" style="object-position:${c.pos}" alt="">
          <div class="txt"><h4>${c.t}</h4><ul>${c.items.map((i) => `<li>${icon("circle-check")}<span>${i}</span></li>`).join("")}</ul></div></div>`
        )
        .join("")}</div>
      <div class="pill primary" style="margin-top:4mm">${icon("store")}حدود ۴۰ هزار نقطه فروش آنلاین و حضوری طرف قرارداد دیجی‌پی برای خرید کارکنان</div>
    </div>${footer(n)}</section>`;
}

function offersHtml(p) {
  if (!p.offers) return "";
  return `<div class="offers">${p.offers
    .map(
      (o) => `<div class="offer"><div class="glyph ${o.blue ? "blue" : ""}">${icon(o.icon).replace('class="ic"', "")}</div>
      <div><span class="tag">${o.tag}</span><div class="amt">${o.amt}</div><div class="term">${o.term}</div></div></div>`
    )
    .join("")}</div>`;
}

function productPageHtml(n, key) {
  const p = products[key];
  const dark = p.dark;
  const media = p.photo
    ? `<div class="media" style="position:relative;overflow:hidden">
      <img class="cover-img" src="${img(p.photo)}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:${p.photoPos || "center"}" alt="">
      ${p.stat ? `<div class="statbox"><div class="big">${p.stat.big}</div><div class="lbl">${p.stat.lbl}</div></div>` : ""}
    </div>`
    : `<div class="media panel">
      ${swoosh({ x: "-25mm", y: "95mm", w: 150, opacity: 0.07 })}
      <div class="panel-icon">${icon(p.panel.icon)}</div>
      <div class="panel-en">${p.panel.en.join("<br>")}</div>
    </div>`;

  const featList = p.features
    ? `<ul class="feat">${p.features.map((f) => `<li>${icon(f.icon)}<span>${f.t}</span></li>`).join("")}</ul>`
    : "";
  const groups = p.groups
    ? `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:2.4mm;margin-top:5mm">${p.groups
        .map((g) => `<div class="pill" style="align-items:flex-start;padding:2.6mm 3mm">${icon(g.icon)}<div><b style="color:var(--navy);font-size:9pt">${g.t}</b><div style="font-size:7.8pt;color:var(--ink-2);line-height:1.6">${g.d}</div></div></div>`)
        .join("")}</div>`
    : "";
  const pills = p.pills
    ? `<div class="pills">${p.pills.map((x) => `<div class="pill ${x.primary ? "primary" : ""}">${icon(x.icon)}<span>${x.t}</span></div>`).join("")}</div>`
    : "";
  const bankNote = p.bankNote ? `<div class="pill primary" style="margin-top:4mm">${icon("landmark")}<span>${p.bankNote}</span></div>` : "";
  const pitch = p.pitch && (p.compactGuide || p.val) ? `<div class="pitch">${icon("messages-square")}<span class="k">پیام کلیدی</span><span>${p.pitch}</span></div>` : "";

  let grid;
  if (p.val) {
    const side = `${offersHtml(p)}${pills}${bankNote}`;
    const top = side
      ? `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8mm;align-items:start"><div>${featList}${groups}</div><div style="margin-top:5mm">${side}</div></div>`
      : groups || featList.replace('class="feat"', 'class="feat" style="grid-template-columns:1fr 1fr;column-gap:8mm"');
    const vcard = (k, title, items) => `<div class="gcard valcard ${k}" style="color:var(--ink)">
        <div class="ghead">${icon(k === "user" ? "user-check" : "sparkles")}<span class="name" style="font-size:9.5pt">${title}</span></div>
        <ul class="v">${items.map((x) => `<li>${x}</li>`).join("")}</ul></div>`;
    const cos = (p.cos || []).map((id) => C.group.find((g) => g.id === id)).filter(Boolean);
    grid = `${top}
      <div style="font-weight:800;color:${dark ? "#fff" : "var(--navy)"};font-size:10pt;margin:4.5mm 0 2.4mm">ارزش‌آفرینی</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:3mm">${vcard("user", "ارزش برای مشتری", p.val.user)}${vcard("group", "ارزش برای دیجی‌پی و گروه", p.val.group)}</div>
      ${cos.length ? `<div class="cochips"><span class="k">هم‌افزایی با گروه</span>${cos.map((g) => `<span class="co">${icon(g.icon)}${g.fa}</span>`).join("")}</div>` : ""}`;
  } else if (p.compactGuide) {
    // top row: features | offers ; below: target-market cards across the full width
    const side = `${offersHtml(p)}${pills}${bankNote}`;
    const top = side
      ? `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8mm;align-items:start"><div>${featList}${groups}</div><div style="margin-top:5mm">${side}</div></div>`
      : groups || featList.replace('class="feat"', 'class="feat" style="grid-template-columns:1fr 1fr;column-gap:8mm"');
    const cards = bySeg(p.compactGuide).map((g) => {
      const s = SEGMENTS[g.seg];
      return `<div class="gcard" style="padding:3.2mm 4mm;gap:1.6mm;color:var(--ink)">
        <div class="ghead" style="padding-bottom:1.6mm">${icon(s.icon)}<span class="name" style="font-size:9.5pt">${s.fa}</span></div>
        <div class="blk"><div class="k">مشتریان هدف</div><div class="v">${g.t}</div></div>
        <div class="blk"><div class="k">نشانه‌های شناسایی</div><div class="v">${g.s}</div></div></div>`;
    });
    if (p.example) cards.push(`<div class="gcard" style="padding:3.2mm 4mm;gap:1.6mm;color:var(--ink)"><div class="blk"><div class="k">نمونه کاربرد</div><div class="example">${p.example}</div></div></div>`);
    grid = `${top}
      <div style="font-weight:800;color:${dark ? "#fff" : "var(--navy)"};font-size:10pt;margin:4.5mm 0 2.4mm">بازار هدف و شاخص شناسایی</div>
      <div style="display:grid;grid-template-columns:repeat(${Math.max(2, cards.length)},1fr);gap:3mm">${cards.join("")}</div>`;
  } else {
    grid = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8mm;margin-top:2mm;align-items:start">
        <div>${featList}${groups}</div>
        <div style="margin-top:6mm">${offersHtml(p)}${pills}${bankNote}</div>
      </div>`;
  }

  return `<section class="page ${dark ? "dark" : ""}" style="display:grid;grid-template-columns:64% 36%">
    <div class="body" style="position:relative;padding:15mm 16mm 20mm 10mm">
      ${dark ? "" : swoosh({ x: "120mm", y: "100mm", w: 120, color: "#15479e", opacity: 0.035 })}
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div class="title-row"><span class="num-badge">${faDigits(p.no)}</span><span class="h-title">${p.title}</span>${p.status ? `<span class="status">${p.status}</span>` : ""}</div>
        <span class="en" style="font-size:9pt;color:${dark ? "rgba(255,255,255,.55)" : "var(--sky)"};padding-top:3mm">${p.en}</span>
      </div>
      <p class="lead" style="font-size:9.6pt">${p.lead}</p>
      ${segChips(p.seg, { onlyActive: true })}
      ${grid}
      ${pitch}
    </div>
    ${media}
    ${footer(n, "")}</section>`;
}

function guidePage(n, key) {
  const p = products[key];
  const G = p.guide;
  const cards = bySeg(G.cards)
    .map((c) => {
      const s = SEGMENTS[c.seg];
      return `<div class="gcard">
        <div class="ghead">${icon(s.icon)}<span class="name">${s.fa}</span><span class="role">${s.role}</span></div>
        <div class="blk"><div class="k">نیاز مشتری</div><div class="v">${c.need}</div></div>
        <div class="blk"><div class="k">کاربرد محصول</div><div class="v">${c.use}</div></div>
        <div class="blk"><div class="k">شاخص‌های شناسایی مشتری</div><ul class="v">${c.signals.map((x) => `<li>${x}</li>`).join("")}</ul></div>
        <div class="blk"><div class="k">صنایع و گروه‌های مرتبط</div><div class="tags">${c.industries.map((x) => `<span>${x}</span>`).join("")}</div></div>
        <div class="blk" style="margin-top:auto"><div class="k">نمونه کاربرد</div><div class="example">${c.example}</div></div>
      </div>`;
    })
    .join("");
  return `<section class="page pale">
    <div class="content" style="inset:13mm 16mm 19mm 16mm">
      <div class="guide-head">
        <div><div class="eyebrow">بازار هدف و راهنمای شناسایی مشتری</div><div class="h-title" style="font-size:16pt">${p.title}</div></div>
        <div class="en" style="font-size:9pt;color:var(--sky)">${p.en} · Target Market</div>
      </div>
      <div class="guide-grid c${G.cols}" style="margin-top:4mm">${cards}</div>
      <div class="pitch">${icon("messages-square")}<span class="k">پیام کلیدی برای مشتری</span><span>${G.pitch}</span></div>
    </div>${footer(n)}</section>`;
}

function toolkitPage(n) {
  const rows = C.toolkit
    .map((r, i) => {
      const s = SEGMENTS[r.seg];
      return `<tr><td class="n">${i + 1}</td><td>${r.sig}</td><td class="seg-c"><span class="seg" style="font-size:7pt">${icon(s.icon)}${s.fa}</span></td><td class="prod">${r.prod}</td><td class="q">${r.q}</td></tr>`;
    })
    .join("");
  return `<section class="page pale">
    <div class="content" style="inset:14mm 16mm 19mm 16mm">
      <div class="h-title">جعبه‌ابزار شعبه: از نشانه تا پیشنهاد</div>
      <div class="h-sub">اگر در شعبه این نشانه‌ها را دیدید، این محصول را پیشنهاد دهید و گفت‌وگو را با این پرسش آغاز کنید.</div>
      <table class="kit"><thead><tr><th></th><th>نشانه در شعبه</th><th>حوزه</th><th>محصول پیشنهادی</th><th>پرسش یا پیام آغاز گفت‌وگو</th></tr></thead><tbody>${rows}</tbody></table>
    </div>${footer(n)}</section>`;
}

function processPage(n) {
  return `<section class="page">
    ${swoosh({ x: "150mm", y: "115mm", w: 170, color: "#15479e", opacity: 0.04 })}
    <div class="content">
      <div class="h-title">فرایند همکاری شعبه و دیجی‌پی</div>
      <div class="h-sub">از شناسایی مشتری در شعبه تا راه‌اندازی خدمت، در پنج گام</div>
      <div class="steps">${C.process
        .map((s, i) => `<div class="step"><div class="sn">${faDigits(i + 1)}</div><h5>${s.t}</h5><p>${s.d}</p><div class="who">${s.who}</div></div>`)
        .join("")}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:5mm;margin-top:10mm">
        <div class="pill primary" style="padding:4.5mm 5mm">${icon("mail")}<div><b>ارجاع مشتری</b><div style="font-size:8.5pt;opacity:.85;margin-top:.5mm">نام مشتری، حوزه، محصول موردنظر و اطلاعات تماس را به <span class="en">${C.contact.email}</span> ارسال کنید.</div></div></div>
        <div class="pill" style="padding:4.5mm 5mm">${icon("phone")}<div><b style="color:var(--navy)">تماس با دیجی‌پی</b><div style="font-size:8.5pt;color:var(--ink-2);margin-top:.5mm"><span class="en">${C.contact.phone}</span> — داخلی‌ها: <span class="en">${C.contact.ext}</span></div></div></div>
      </div>
    </div>${footer(n)}</section>`;
}

function valuePage(n) {
  return `<section class="page navy">
    ${swoosh({ x: "-30mm", y: "120mm", w: 160, opacity: 0.05 })}
    <div class="content">
      <div class="h-title">ارزش همکاری برای بانک تجارت</div>
      <div class="h-sub">ارائه محصولات دیجی‌پی به مشتریان، فقط یک خدمت جدید نیست؛ ابزاری برای رشد منابع، تسهیلات و وفاداری مشتریان بانک است.</div>
      <div class="vgrid">${C.bankValue.map((v) => `<div class="vcard">${icon(v.icon)}<h5>${v.t}</h5><p>${v.d}</p></div>`).join("")}</div>
    </div>${footer(n)}</section>`;
}

function capacityPage(n) {
  return `<section class="page pale">
    <div class="content">
      <div class="h-title">ظرفیت‌های قابل توسعه با بانک تجارت</div>
      <div class="h-sub">فرصت‌هایی که با اتکا به زیرساخت فعلی دیجی‌پی، امکان ارائه آن‌ها به مشتریان بانک تجارت وجود دارد و پیشنهاد می‌شود در قالب همکاری مشترک بررسی شود.</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4mm;margin-top:8mm">${C.capacities
        .map((c) => `<div class="idea">${icon(c.icon)}<div><h5>${c.t}</h5><p>${c.d}</p>${segChips(Object.fromEntries(c.segs.map((s) => [s, "full"])), { onlyActive: true })}</div></div>`)
        .join("")}</div>
    </div>${footer(n)}</section>`;
}

function clientsPage(n) {
  return `<section class="page" style="display:grid;grid-template-columns:1fr 1.25fr;align-items:center">
    <div style="padding:0 20mm 0 6mm">
      <div class="h-title" style="font-size:24pt;color:var(--bright);line-height:1.5">سازمان‌های بزرگی که<br>به ما اعتماد کرده‌اند</div>
      <p class="lead">برخی از سازمان‌ها و شرکت‌های همکار دیجی‌پی</p>
    </div>
    <div class="cgrid">${JSON.parse(readFileSync(path.join(ROOT, "assets/clients/clients.json"), "utf8"))
      .map((c) => `<div class="c"><img src="assets/clients/${c.id}.png" alt="${c.fa}"></div>`)
      .join("")}</div>
    ${footer(n)}</section>`;
}

function contactPage(n) {
  return `<section class="page navy" style="display:grid;grid-template-columns:1fr 1fr">
    <div style="position:relative;padding:0 20mm;display:flex;flex-direction:column;justify-content:center">
      <div class="h-title" style="font-size:22pt">راه‌های ارتباطی</div>
      <div class="h-sub">شرکت نوآوران پرداخت مجازی ایرانیان (دیجی‌پی)</div>
      <div class="contact-list">
        <div class="r">${icon("phone")}<span class="k">شماره تماس</span><span class="v">${C.contact.phone}</span></div>
        <div class="r">${icon("users")}<span class="k">داخلی‌ها</span><span class="v">${C.contact.ext}</span></div>
        <div class="r">${icon("mail")}<span class="k">ایمیل</span><span class="v">${C.contact.email}</span></div>
        <div class="r">${icon("globe")}<span class="k">وب‌سایت</span><span class="v">${C.contact.web}</span></div>
      </div>
    </div>
    <div style="position:relative;overflow:hidden"><img src="${img("storefront.jpg")}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover" alt=""></div>
    ${footer(n, "half")}</section>`;
}

function backPage() {
  return `<section class="page bright cover">
    ${swoosh({ x: "60mm", y: "40mm", w: 180, opacity: 0.07 })}
    <div class="inner"><img class="logo" style="width:70mm" src="${img("logo-white.png")}" alt="digipay">
      <div class="en" style="margin-top:8mm;letter-spacing:.12em;font-size:10pt;opacity:.9">${C.contact.web}</div></div>
  </section>`;
}

// ---------------------------------------------------------------- board-edition templates
function introBoardPage(n) {
  const I = C.intro;
  return `<section class="page">
    ${swoosh({ x: "190mm", y: "110mm", w: 150, color: "#15479e", opacity: 0.04 })}
    <div class="content">
      <div class="h-title">${I.title}</div>
      <p class="lead" style="max-width:215mm;font-size:10.5pt">${I.lead}</p>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:5mm;margin-top:10mm">${I.points
        .map((h, i) => `<div class="idea">${icon(h.icon)}<div><h5>${faDigits(i + 1)}. ${h.t}</h5><p>${h.d}</p></div></div>`)
        .join("")}</div>
      <div class="statrow" style="margin-top:12mm">${[
        { n: "12+", t: "میلیون کاربر" },
        { n: "50+", t: "همت اعتبار اعطاشده در سال ۱۴۰۴" },
        { n: "40K", t: "نقطه فروش آنلاین و حضوری" },
        { n: "15", t: "محصول در سه گروه مشتری" },
      ].map((x) => `<div><span class="n">${x.n}</span><span class="t">${x.t}</span></div>`).join("")}</div>
    </div>${footer(n)}</section>`;
}

function b2oOverviewPage(n) {
  const why = [
    { icon: "user-check", t: "کاربران شناسایی‌شده", d: "کاربرانی که از مسیر سازمان وارد می‌شوند معمولاً احراز هویت‌شده‌اند و درآمد مشخصی دارند." },
    { icon: "shield-check", t: "ریسک اعتباری پایین", d: "ضمانت سازمان، کسر اقساط از حقوق و جمع‌آوری سیستمی، اعتباردهی بدون چک و سفته فردی را ممکن می‌کند." },
    { icon: "refresh-cw", t: "رابطه مالی مستمر", d: "دیجی‌کارت و بن رفاهی، رابطه کاربر را از یک ثبت‌نام مقطعی به خرید و تراکنش مستمر می‌رساند." },
  ];
  const funnel = [
    { icon: "building-2", t: "سازمان", d: "قرارداد و بودجه" },
    { icon: "users", t: "کارکنان و اعضا", d: "کاربران باکیفیت" },
    { icon: "layers", t: "رفاه، اعتبار و وام", d: "بن، ۱ و ۴ قسطه، وام بانکی" },
    { icon: "shopping-cart", t: "خرید در گروه", d: "دیجی‌کالا، جت و پذیرندگان" },
    { icon: "repeat", t: "تراکنش مستمر", d: "رابطه مالی بلندمدت" },
  ];
  const stats = [
    { n: "1&4", t: "اعتبار یک و چهار قسطه کارکنان" },
    { n: "300", t: "میلیون تومان سقف اعتبار سازمانی" },
    { n: "400", t: "میلیون تومان وام بانکی ۱۲ و ۲۴ ماهه" },
    { n: "40K", t: "نقطه فروش برای خرید کارکنان" },
  ];
  return `<section class="page pale">
    <div class="content">
      <div class="eyebrow" style="font-size:8.5pt;color:var(--bright);font-weight:700">تمرکز سند</div>
      <div class="h-title">چرا راهکارهای سازمانی (B2O)؟</div>
      <p class="lead" style="max-width:220mm">ارزش B2O فقط عقد قرارداد با یک سازمان نیست؛ هر سازمان می‌تواند دروازه ورود تعداد زیادی کاربر باکیفیت به دیجی‌پی و گروه دیجی‌کالا باشد. B2O به خدمات رفاهی محدود نمی‌شود و اعتبارهای یک و چهار قسطه، وام‌های بلندمدت بانکی و مدل‌های اعتباردهی حرفه‌ای را هم در بر می‌گیرد.</p>
      <div class="funnel">${funnel.map((f, i) => `<div class="fs">${icon(f.icon)}<b>${f.t}</b><span>${f.d}</span></div>${i < funnel.length - 1 ? `<div class="fa">${icon("arrow-left")}</div>` : ""}`).join("")}</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4mm;margin-top:6mm">${why.map((w) => `<div class="idea">${icon(w.icon)}<div><h5>${w.t}</h5><p>${w.d}</p></div></div>`).join("")}</div>
      <div class="statrow">${stats.map((s) => `<div><span class="n">${s.n}</span><span class="t">${s.t}</span></div>`).join("")}</div>
    </div>${footer(n)}</section>`;
}

function deepDivePage(n, key) {
  const p = products[key];
  const D = p.deep;
  const col = (ic, t, items) => `<div class="gcard valcard"><div class="ghead">${icon(ic)}<span class="name">${t}</span></div><ul class="v">${items.map((x) => `<li>${x}</li>`).join("")}</ul></div>`;
  return `<section class="page pale deep">
    <div class="content" style="inset:14mm 16mm 19mm 16mm">
      <div class="guide-head">
        <div><div class="eyebrow">سازوکار و ارزش‌آفرینی</div><div class="h-title" style="font-size:16pt">${p.title}</div></div>
        <div class="en" style="font-size:9pt;color:var(--sky)">${p.en} · How it works</div>
      </div>
      <div class="flow">${D.flow.map((f, i) => `<div class="st"><div class="sn">${faDigits(i + 1)}</div><h5>${f.t}</h5><p>${f.d}</p></div>`).join("")}</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4mm;margin-top:6mm">
        ${col("building-2", "ارزش برای سازمان", D.values.org)}
        ${col("user-check", "ارزش برای کارکنان و اعضا", D.values.user)}
        ${col("sparkles", "ارزش برای دیجی‌پی و گروه", D.values.group)}
      </div>
      <div class="pitch">${icon("network")}<span class="k">هم‌افزایی با گروه</span><span>${D.synergy}</span></div>
    </div>${footer(n)}</section>`;
}

function ecosystemPage(n) {
  const G = C.group;
  const R = 56, cx = 75, cy = 72;
  const pos = G.map((g, i) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / G.length;
    return { ...g, x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });
  const lines = pos.map((q) => `<line x1="${cx}" y1="${cy}" x2="${q.x}" y2="${q.y}" stroke="#879fcf" stroke-width=".35" stroke-dasharray="1.2 1.2"/>`).join("");
  const nodes = pos.map((q) => `<div class="node" style="left:${q.x}mm;top:${q.y}mm">${icon(q.icon)}<b>${q.fa}</b><span>${q.role}</span></div>`).join("");
  const roles = [
    { icon: "credit-card", t: "زیرساخت پرداخت و اعتبار", d: "کیف پول، BNPL و خرید اقساطی با وام بانکی در چک‌اوت پلتفرم‌های گروه" },
    { icon: "store", t: "تأمین مالی فروشندگان", d: "سرمایه در گردش و تسویه زودهنگام برای فروشندگان بازارگاه" },
    { icon: "building-2", t: "کانال سازمانی", d: "B2O؛ ورود کارکنان سازمان‌ها به خرید مستمر در گروه" },
    { icon: "database", t: "داده مالی مشترک", d: "رفتار خرید و بازپرداخت برای اعتبارسنجی دقیق‌تر" },
  ];
  return `<section class="page" style="display:grid;grid-template-columns:1fr 1.15fr">
    <div style="padding:18mm 18mm 20mm 6mm">
      <div class="h-title">دیجی‌پی در اکوسیستم گروه دیجی‌کالا</div>
      <p class="lead">دیجی‌پی، بازوی فناوری مالی گروه دیجی‌کالاست؛ پرداخت، اعتبار و خدمات مالی را به همه پلتفرم‌های گروه و میلیون‌ها کاربر آن‌ها می‌رساند.</p>
      <div style="display:grid;gap:3mm;margin-top:6mm">${roles.map((r) => `<div class="pill" style="padding:3mm 4mm">${icon(r.icon)}<div><b style="color:var(--navy)">${r.t}</b><div style="font-size:8pt;color:var(--ink-2)">${r.d}</div></div></div>`).join("")}</div>
    </div>
    <div class="hub">
      <svg viewBox="0 0 150 150" style="position:absolute;inset:0;width:150mm;height:150mm">${lines}<circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="#dde5f3" stroke-width=".3"/></svg>
      <div class="center" style="left:${cx}mm;top:${cy}mm"><img src="${img("logo-white.png")}" alt="digipay"></div>
      ${nodes}
    </div>
    ${footer(n)}</section>`;
}

function synergyMatrixPage(n) {
  const G = C.group;
  const cell = (v) => (v === "a" ? `<span class="sy a"></span>` : v === "o" ? `<span class="sy o"></span>` : `<span class="dot none"></span>`);
  const head = G.map((g) => `<th>${icon(g.icon)}<br>${g.fa}</th>`).join("");
  const rows = C.synergyMatrix.map((r) => `<tr><td class="p">${r.p}</td>${G.map((g) => `<td>${cell(r.c[g.id])}</td>`).join("")}</tr>`).join("");
  return `<section class="page symat">
    <div class="content">
      <div class="h-title">نقشه هم‌افزایی با شرکت‌های گروه</div>
      <div class="h-sub">هم‌افزایی‌های فعال و فرصت‌های توسعه محصولات دیجی‌پی در پلتفرم‌های گروه دیجی‌کالا</div>
      <table class="matrix symatrix"><thead><tr><th style="width:22%;text-align:right">محصول دیجی‌پی</th>${head}</tr></thead><tbody>${rows}</tbody></table>
      <div class="legend"><span><span class="sy a"></span> هم‌افزایی فعال</span><span><span class="sy o"></span> فرصت توسعه</span></div>
    </div>${footer(n)}</section>`;
}

function synergyIdeasPage(n) {
  const byId = Object.fromEntries(C.group.map((g) => [g.id, g]));
  return `<section class="page pale">
    <div class="content">
      <div class="h-title">فرصت‌های کلیدی هم‌افزایی</div>
      <div class="h-sub">مسیرهایی که با اتکا به زیرساخت فعلی دیجی‌پی، ارزش بیشتری برای گروه دیجی‌کالا خلق می‌کنند.</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4mm;margin-top:8mm">${C.synergyIdeas
        .map((c) => `<div class="idea">${icon(c.icon)}<div><h5>${c.t}</h5><p>${c.d}</p><div class="cochips" style="margin-top:2.5mm">${c.cos.map((id) => `<span class="co">${icon(byId[id].icon)}${byId[id].fa}</span>`).join("")}</div></div></div>`)
        .join("")}</div>
    </div>${footer(n)}</section>`;
}

function flywheelPage(n) {
  const F = C.flywheel;
  const R = 62, cx = 80, cy = 74;
  const pos = F.map((f, i) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / F.length;
    return { ...f, x: cx + R * Math.cos(a), y: cy + R * Math.sin(a), a };
  });
  // arrowheads at mid-arc between nodes
  const arrows = pos.map((q, i) => {
    const a = q.a + Math.PI / F.length;
    const x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
    const deg = (a * 180) / Math.PI + 90;
    return `<path d="M-2 -1.6 L1.6 0 L-2 1.6" transform="translate(${x} ${y}) rotate(${deg})" fill="none" stroke="#fff" stroke-width=".8" stroke-linecap="round" stroke-linejoin="round"/>`;
  }).join("");
  return `<section class="page navy" style="display:grid;grid-template-columns:1fr 1.25fr">
    ${swoosh({ x: "-30mm", y: "130mm", w: 150, opacity: 0.05 })}
    <div style="position:relative;padding:20mm 18mm 20mm 4mm">
      <div class="h-title">چرخه ارزش دیجی‌پی در گروه</div>
      <p class="lead" style="font-size:10pt">هر خرید با اعتبار دیجی‌پی، داده و منابع بیشتری برای اعتبار بیشتر می‌سازد؛ و اعتبار بیشتر، خرید بیشتر در پلتفرم‌های گروه و شبکه پذیرندگان.</p>
      <div class="pill primary" style="margin-top:6mm;background:#fff;color:var(--navy)">${icon("refresh-cw")}<span>موجودی نقد دیجی‌کارت و وجوه حق بیمه، منابع کم‌هزینه برای توسعه BNPL و خرید اقساطی با وام بانکی فراهم می‌کنند.</span></div>
      ${C.summary ? `<div class="fsum"><div class="k">جمع‌بندی</div>${C.summary.map((v) => `<div class="r">${icon(v.icon)}<div><b>${v.t}</b><span>${v.d}</span></div></div>`).join("")}</div>` : ""}
    </div>
    <div class="hub fly">
      <svg viewBox="0 0 160 150" style="position:absolute;inset:0;width:160mm;height:150mm"><circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="rgba(255,255,255,.35)" stroke-width=".5"/>${arrows}</svg>
      <div class="center" style="left:${cx}mm;top:${cy}mm;width:38mm;height:38mm;background:#fff"><span style="color:var(--navy);font-weight:800;font-size:9pt;line-height:1.6;text-align:center">چرخه ارزش<br>دیجی‌پی</span></div>
      ${pos.map((q, i) => `<div class="node light" style="left:${q.x}mm;top:${q.y}mm">${icon(q.icon)}<b>${faDigits(i + 1)}. ${q.t}</b><span>${q.d}</span></div>`).join("")}
    </div>
    ${footer(n)}</section>`;
}

function summaryPage(n) {
  return `<section class="page navy summ">
    ${swoosh({ x: "-30mm", y: "120mm", w: 160, opacity: 0.05 })}
    <div class="content">
      <div class="h-title">جمع‌بندی</div>
      <div class="h-sub">دیجی‌پی؛ نخستین فناوری مالی جامع در ایران و بازوی مالی گروه دیجی‌کالا</div>
      <div class="vgrid" style="grid-template-columns:repeat(2,1fr)">${C.summary.map((v) => `<div class="vcard">${icon(v.icon)}<h5>${v.t}</h5><p>${v.d}</p></div>`).join("")}</div>
    </div>${footer(n)}</section>`;
}


function multiProductPage(n, keys, eyebrow, { tall = false } = {}) {
  const cards = keys.map((k) => {
    const p = products[k];
    const feats = (p.features || (p.groups || []).map((g) => ({ icon: g.icon, t: `${g.t}؛ ${g.d}` }))).slice(0, 4);
    const pill = (p.pills || []).find((x) => x.primary);
    const cos = (p.cos || []).map((id) => C.group.find((g) => g.id === id)).filter(Boolean);
    return `<div class="mcard">
      <img class="mimg" src="${img(p.photo)}" style="object-position:${p.bandPos || "center 55%"}" alt="">
      <div class="mbody">
        <div class="mhead"><span class="num-badge">${faDigits(p.no)}</span><div><div class="mt">${p.title}${p.status ? `<span class="status">${p.status}</span>` : ""}</div><div class="en">${p.en}</div></div></div>
        <p class="mlead">${p.lead}</p>
        ${segChips(p.seg, { onlyActive: true })}
        <ul class="feat">${feats.map((f) => `<li>${icon(f.icon)}<span>${f.t}</span></li>`).join("")}</ul>
        ${p.offers && !p.val ? `<div class="moffers">${p.offers.map((o) => `<span><i>${o.tag}</i><div>${o.amt}</div><em>${o.term}</em></span>`).join("")}</div>` : ""}
        ${pill ? `<div class="pill primary">${icon(pill.icon)}<span>${pill.t}</span></div>` : ""}
        ${p.val ? `<div class="mval"><div class="k">${icon("sparkles")}ارزش برای دیجی‌پی و گروه</div><ul>${p.val.group.map((x) => `<li>${x}</li>`).join("")}</ul></div>` : ""}
        ${cos.length ? `<div class="cochips"><span class="k">هم‌افزایی با گروه</span>${cos.map((g) => `<span class="co">${icon(g.icon)}${g.fa}</span>`).join("")}</div>` : ""}
      </div>
    </div>`;
  });
  return `<section class="page pale multi${tall ? " tall" : ""}">
    <div class="content" style="inset:11mm 13mm 18mm 13mm">
      <div class="eyebrow">${eyebrow}</div>
      <div class="mcols c${keys.length}">${cards.join("")}</div>
    </div>${footer(n)}</section>`;
}

// ---------------------------------------------------------------- assemble
function addSections({ deep }) {
  sections.forEach((sec, si) => {
    add(
      (n) =>
        divider(n, {
          title: sec.title, en: sec.en, desc: sec.desc, kicker: `بخش ${faDigits(si + 1)}`, big: `0${si + 1}`,
          related: sections
            .filter((o) => o.id !== sec.id)
            .flatMap((o) => o.products)
            .filter((k) => products[k].seg[sec.id] === "full")
            .map((k) => ({ title: products[k].title, pg: productPage[k] })),
        }),
      { label: sec.title, level: "sec" }
    );
    if (deep && sec.id === "org") {
      add((n) => b2oOverviewPage(n), { label: "چرا راهکارهای سازمانی (B2O)؟", level: "sub" });
      add((n) => clientsPage(n), { label: "سازمان‌های همکار", level: "sub" });
    }
    sec.products.forEach((k) => {
      const p = products[k];
      p.no = ++productNo;
      productPage[k] = pages.length + 1;
      if (k === "welfare") add((n) => welfarePage(n, k), { label: p.title, level: "sub" });
      else add((n) => productPageHtml(n, k), { label: p.title, level: "sub" });
      if (p.guide) add((n) => guidePage(n, k));
      if (deep && p.deep) add((n) => deepDivePage(n, k));
    });
  });
}

add(() => cover());
if (!BOARD) add((n) => toc(n));
if (BOARD) {
  // board deck (max 25 pages): section dividers kept, B2O in depth, other products 2-3 per page
  const S = Object.fromEntries(sections.map((x) => [x.id, x]));
  sections.forEach((sec) => sec.products.forEach((k) => (products[k].no = ++productNo)));
  const secDivider = (sid, si) => (n) =>
    divider(n, {
      title: S[sid].title, en: S[sid].en, desc: S[sid].desc, kicker: `بخش ${faDigits(si)}`, big: `0${si}`,
      related: sections
        .filter((o) => o.id !== sid)
        .flatMap((o) => o.products)
        .filter((k) => products[k].seg[sid] === "full")
        .map((k) => ({ title: products[k].title, pg: productPage[k] })),
    });
  const multi = (keys, sid, opts = {}) => {
    keys.forEach((k) => (productPage[k] = pages.length + 1));
    add((n) => multiProductPage(n, keys, S[sid].title, opts));
  };
  add((n) => divider(n, { title: "دیجی‌پی در یک نگاه", en: ["Digipay", "at a glance"] }));
  add((n) => glancePage(n));
  add((n) => merchantsPage(n));
  add((n) => matrixPage(n));
  // 1. B2O
  add(secDivider("org", 1));
  add((n) => b2oOverviewPage(n));
  add((n) => clientsPage(n));
  ["welfare", "orgbnpl"].forEach((k) => {
    productPage[k] = pages.length + 1;
    add((n) => (k === "welfare" ? welfarePage(n, k) : productPageHtml(n, k)));
    add((n) => deepDivePage(n, k));
  });
  multi(["orgloan", "procredit"], "org", { tall: true });
  add((n) => deepDivePage(n, "orgloan"));
  // 2. businesses
  add(secDivider("biz", 2));
  multi(["merchantbnpl", "workingcapital"], "biz");
  multi(["earlysettlement", "adservice"], "biz");
  // 3. individuals
  add(secDivider("retail", 3));
  multi(["bnpl", "ccredit"], "retail");
  multi(["digicard", "wealth", "insurance"], "retail");
  multi(["daily", "crypto"], "retail");
  // 4. synergy
  add((n) => divider(n, { title: "هم‌افزایی در گروه دیجی‌کالا", en: ["Digikala Group", "Synergy"], desc: "جایگاه دیجی‌پی در اکوسیستم گروه، فرصت‌های کلیدی هم‌افزایی و چرخه ارزش.", kicker: `بخش ${faDigits(4)}`, big: "04" }));
  add((n) => ecosystemPage(n));
  add((n) => synergyIdeasPage(n));
  add((n) => flywheelPage(n));
} else {
  add((n) => introPage(n), { label: "درباره این سند", level: "" });
  add((n) => divider(n, { title: "دیجی‌پی در یک نگاه", en: ["Digipay", "at a glance"] }), { label: "دیجی‌پی در یک نگاه", level: "sec" });
  add((n) => glancePage(n), { label: "آمار، خدمات و دنیای کالا", level: "sub" });
  add((n) => networkPage(n), { label: "شبکه پذیرندگان دیجی‌پی", level: "sub" });
  add((n) => merchantsPage(n), { label: "برخی از پذیرندگان طرف قرارداد", level: "sub" });
  add((n) => matrixPage(n), { label: "نقشه محصولات به تفکیک حوزه بانکداری", level: "sec" });
  addSections({ deep: false });
  add((n) => divider(n, { title: "راهنمای عملیاتی شعب", en: ["Branch", "Toolkit"], desc: "ابزارهای کاربردی برای شناسایی مشتریان، ارجاع و پیگیری همکاری.", kicker: `بخش ${faDigits(sections.length + 1)}`, big: `0${sections.length + 1}` }), { label: "راهنمای عملیاتی شعب", level: "sec" });
  add((n) => toolkitPage(n), { label: "جعبه‌ابزار شعبه: از نشانه تا پیشنهاد", level: "sub" });
  add((n) => processPage(n), { label: "فرایند همکاری شعبه و دیجی‌پی", level: "sub" });
  add((n) => valuePage(n), { label: "ارزش همکاری برای بانک تجارت", level: "sub" });
  add((n) => capacityPage(n), { label: "ظرفیت‌های قابل توسعه", level: "sub" });
  add((n) => clientsPage(n), { label: "سازمان‌های همکار", level: "sub" });
  add((n) => contactPage(n), { label: "راه‌های ارتباطی", level: "sec" });
  add(() => backPage());
}

const body = pages.map((p, i) => p.render(i + 1)).join("\n");
let html = `<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${C.meta.title} — ${C.meta.subtitle}</title>
<link rel="stylesheet" href="src/styles.css">
</head><body>
${body}
</body></html>`;
if (NONUM) html = (await import("./src/nonum.mjs")).stripNumbers(html);
const HTML_FILE = BOARD ? "index-board.html" : NONUM ? "index-nonum.html" : "index.html";
writeFileSync(path.join(ROOT, HTML_FILE), html);
console.log(`${HTML_FILE}: ${pages.length} pages`);

if (process.argv.includes("--html")) process.exit(0);

// ---------------------------------------------------------------- pdf
const globalRoot = execSync("npm root -g").toString().trim();
const require = createRequire(path.join(globalRoot, "noop.js"));
const { chromium } = require("playwright");
mkdirSync(path.join(ROOT, "dist"), { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(pathToFileURL(path.join(ROOT, HTML_FILE)).href, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
const out = path.join(ROOT, "dist", C.meta.out || (NONUM ? "digipay-tejarat-brochure-no-figures.pdf" : "digipay-tejarat-brochure.pdf"));
await page.pdf({ path: out, width: "297mm", height: "210mm", printBackground: true, preferCSSPageSize: true });
if (process.argv.includes("--png")) {
  const PREV = BOARD ? "dist/preview-board" : NONUM ? "dist/preview-nonum" : "dist/preview";
  rmSync(path.join(ROOT, PREV), { recursive: true, force: true });
  mkdirSync(path.join(ROOT, PREV), { recursive: true });
  await page.setViewportSize({ width: 1123, height: 794 });
  const els = await page.$$("section.page");
  for (let i = 0; i < els.length; i++) await els[i].screenshot({ path: path.join(ROOT, `${PREV}/p${String(i + 1).padStart(2, "0")}.png`) });
}
await browser.close();
console.log("pdf:", out);
