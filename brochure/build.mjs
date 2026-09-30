// Builds index.html from src/content.mjs and renders dist/*.pdf with Playwright/Chromium.
//   node build.mjs          -> html + pdf
//   node build.mjs --html   -> html only
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import * as C from "./src/content.mjs";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const { SEGMENTS, products, sections } = C;

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
      <div class="partner"><span>قدرت گرفته از</span><img src="${img("tejarat-white.png")}" alt="بانک تجارت"><span class="sep"></span><img src="${img("digikala-white.png")}" alt="دیجی‌کالا"></div>
    </div>
    <div class="date">${C.meta.date}</div>
  </section>`;
}

function toc(n) {
  const rows = pages
    .map((p, i) => (p.toc ? { ...p.toc, pg: i + 1 } : null))
    .filter(Boolean);
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

function divider(n, { title, en, desc, kicker, big, image }) {
  if (image) {
    return `<section class="page navy divider" style="display:grid;grid-template-columns:1fr 1fr">
      <div style="position:relative">
        <div class="title-block">${kicker ? `<div class="kicker">${kicker}</div>` : ""}<h2>${title}</h2><div class="ghost">${en.join("<br>")}</div>${desc ? `<p class="desc">${desc}</p>` : ""}</div>
      </div>
      <div style="background:url(${img(image)}) center/cover"></div>
      ${footer(n, "")}</section>`;
  }
  return `<section class="page navy divider">
    ${swoosh({ x: "-20mm", y: "105mm", w: 170, opacity: 0.05 })}
    <div class="title-block">${kicker ? `<div class="kicker">${kicker}</div>` : ""}<h2>${title}</h2><div class="ghost">${en.join("<br>")}</div>${desc ? `<p class="desc">${desc}</p>` : ""}</div>
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
        <div class="p"><img src="${img("tejarat-white.png")}" alt=""><span>قدرت گرفته از بانک تجارت</span></div>
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
  return `<section class="page navy" style="display:grid;grid-template-columns:1fr 1fr">
    <div style="position:relative;padding:18mm 16mm 20mm 14mm">
      <div class="h-title">برخی از فروشگاه‌های طرف قرارداد دیجی‌پی</div>
      <p class="lead" style="font-size:9.5pt">شبکه‌ای از ویترین‌های آنلاین و حضوری در سراسر کشور؛ از دیجی‌کالا تا فروشگاه‌های تخصصی در هر شهر.</p>
      <img src="${img("merchants.jpg")}" style="width:100%;margin-top:7mm;border-radius:3mm" alt="">
    </div>
    <div style="position:relative;background:url(${img("map.jpg")}) center/cover">
      <div class="statbox" style="top:auto;bottom:24mm"><div class="big">500</div><div class="lbl">هزار ویترین فروش آنلاین و حضوری</div></div>
    </div>
    ${footer(n, "half")}</section>`;
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
      return `<tr><td class="grp" colspan="6">${sec.title}</td></tr>${rows}`;
    })
    .join("");
  return `<section class="page">
    <div class="content">
      <div class="h-title">نقشه محصولات به تفکیک حوزه بانکداری</div>
      <div class="h-sub">هر محصول برای کدام گروه از مشتریان بانک تجارت کاربرد دارد؟</div>
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
          (c) => `<div class="card"><div class="img" style="background-image:url(${img(c.img)});background-position:${c.pos}"></div>
          <div class="txt"><h4>${c.t}</h4><ul>${c.items.map((i) => `<li>${icon("circle-check")}<span>${i}</span></li>`).join("")}</ul></div></div>`
        )
        .join("")}</div>
      <div class="pill primary" style="margin-top:4mm">${icon("store")}ده‌ها هزار فروشگاه آنلاین و حضوری طرف قرارداد دیجی‌پی برای خرید کارکنان</div>
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
      <img class="cover-img" src="${img(p.photo)}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover" alt="">
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
  const pitch = p.pitch && p.compactGuide ? `<div class="pitch">${icon("messages-square")}<span class="k">پیام کلیدی</span><span>${p.pitch}</span></div>` : "";

  let grid;
  if (p.compactGuide) {
    // top row: features | offers ; below: target-market cards across the full width
    const side = `${offersHtml(p)}${pills}${bankNote}`;
    const top = side
      ? `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8mm;align-items:start"><div>${featList}${groups}</div><div style="margin-top:5mm">${side}</div></div>`
      : groups || featList.replace('class="feat"', 'class="feat" style="grid-template-columns:1fr 1fr;column-gap:8mm"');
    const cards = p.compactGuide.map((g) => {
      const s = SEGMENTS[g.seg];
      return `<div class="gcard" style="padding:3.2mm 4mm;gap:1.6mm;color:var(--ink)">
        <div class="ghead" style="padding-bottom:1.6mm">${icon(s.icon)}<span class="name" style="font-size:9.5pt">${s.fa}</span></div>
        <div class="blk"><div class="k">مشتریان هدف</div><div class="v">${g.t}</div></div>
        <div class="blk"><div class="k">نشانه‌های شناسایی</div><div class="v">${g.s}</div></div></div>`;
    });
    if (p.example) cards.push(`<div class="gcard" style="padding:3.2mm 4mm;gap:1.6mm;color:var(--ink)"><div class="blk"><div class="k">نمونه کاربرد</div><div class="example">${p.example}</div></div></div>`);
    grid = `${top}
      <div style="font-weight:800;color:${dark ? "#fff" : "var(--navy)"};font-size:10pt;margin:6mm 0 2.4mm">بازار هدف و شاخص شناسایی</div>
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
  const cards = G.cards
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
        <div class="pill" style="padding:4.5mm 5mm">${icon("phone")}<div><b style="color:var(--navy)">تماس با تیم فروش سازمانی</b><div style="font-size:8.5pt;color:var(--ink-2);margin-top:.5mm"><span class="en">${C.contact.phone}</span> — داخلی‌ها: <span class="en">${C.contact.ext}</span></div></div></div>
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
      <p class="lead">برخی از سازمان‌های طرف قرارداد دیجی‌پی در ارائه راهکارهای سازمانی</p>
    </div>
    <div style="padding:0 6mm 0 16mm"><img src="${img("clients.png")}" style="width:100%" alt=""></div>
    ${footer(n)}</section>`;
}

function contactPage(n) {
  return `<section class="page navy" style="display:grid;grid-template-columns:1fr 1fr">
    <div style="position:relative;padding:0 20mm;display:flex;flex-direction:column;justify-content:center">
      <div class="h-title" style="font-size:22pt">راه‌های ارتباطی</div>
      <div class="h-sub">تیم فروش سازمانی دیجی‌پی</div>
      <div class="contact-list">
        <div class="r">${icon("phone")}<span class="k">شماره تماس</span><span class="v">${C.contact.phone}</span></div>
        <div class="r">${icon("users")}<span class="k">داخلی‌ها</span><span class="v">${C.contact.ext}</span></div>
        <div class="r">${icon("mail")}<span class="k">ایمیل</span><span class="v">${C.contact.email}</span></div>
        <div class="r">${icon("globe")}<span class="k">وب‌سایت</span><span class="v">${C.contact.web}</span></div>
      </div>
    </div>
    <div style="background:url(${img("storefront.jpg")}) center/cover"></div>
    ${footer(n, "half")}</section>`;
}

function backPage() {
  return `<section class="page bright cover">
    ${swoosh({ x: "60mm", y: "40mm", w: 180, opacity: 0.07 })}
    <div class="inner"><img class="logo" style="width:70mm" src="${img("logo-white.png")}" alt="digipay">
      <div class="en" style="margin-top:8mm;letter-spacing:.12em;font-size:10pt;opacity:.9">${C.contact.web}</div></div>
  </section>`;
}

// ---------------------------------------------------------------- assemble
add(() => cover());
add((n) => toc(n));
add((n) => introPage(n), { label: "درباره این سند", level: "" });
add((n) => divider(n, { title: "دیجی‌پی در یک نگاه", en: ["Digipay", "at a glance"] }), { label: "دیجی‌پی در یک نگاه", level: "sec" });
add((n) => glancePage(n), { label: "آمار، خدمات و دنیای کالا", level: "sub" });
add((n) => networkPage(n), { label: "شبکه فروشگاه‌های طرف قرارداد", level: "sub" });
add((n) => matrixPage(n), { label: "نقشه محصولات به تفکیک حوزه بانکداری", level: "sec" });

sections.forEach((sec, si) => {
  add((n) => divider(n, { title: sec.title, en: sec.en, desc: sec.desc, kicker: `بخش ${faDigits(si + 1)}`, big: `0${si + 1}` }), { label: sec.title, level: "sec" });
  sec.products.forEach((k) => {
    const p = products[k];
    p.no = ++productNo;
    productPage[k] = pages.length + 1;
    if (k === "welfare") add((n) => welfarePage(n, k), { label: p.title, level: "sub" });
    else add((n) => productPageHtml(n, k), { label: p.title, level: "sub" });
    if (p.guide) add((n) => guidePage(n, k));
  });
});

add((n) => divider(n, { title: "راهنمای عملیاتی شعب", en: ["Branch", "Toolkit"], desc: "ابزارهای کاربردی برای شناسایی مشتریان، ارجاع و پیگیری همکاری.", kicker: `بخش ${faDigits(sections.length + 1)}`, big: `0${sections.length + 1}` }), { label: "راهنمای عملیاتی شعب", level: "sec" });
add((n) => toolkitPage(n), { label: "جعبه‌ابزار شعبه: از نشانه تا پیشنهاد", level: "sub" });
add((n) => processPage(n), { label: "فرایند همکاری شعبه و دیجی‌پی", level: "sub" });
add((n) => valuePage(n), { label: "ارزش همکاری برای بانک تجارت", level: "sub" });
add((n) => capacityPage(n), { label: "ظرفیت‌های قابل توسعه", level: "sub" });
add((n) => clientsPage(n), { label: "سازمان‌های طرف قرارداد", level: "sub" });
add((n) => contactPage(n), { label: "راه‌های ارتباطی", level: "sec" });
add(() => backPage());

const body = pages.map((p, i) => p.render(i + 1)).join("\n");
const html = `<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${C.meta.title} — ${C.meta.subtitle}</title>
<link rel="stylesheet" href="src/styles.css">
</head><body>
${body}
</body></html>`;
writeFileSync(path.join(ROOT, "index.html"), html);
console.log(`index.html: ${pages.length} pages`);

if (process.argv.includes("--html")) process.exit(0);

// ---------------------------------------------------------------- pdf
const globalRoot = execSync("npm root -g").toString().trim();
const require = createRequire(path.join(globalRoot, "noop.js"));
const { chromium } = require("playwright");
mkdirSync(path.join(ROOT, "dist"), { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(pathToFileURL(path.join(ROOT, "index.html")).href, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
const out = path.join(ROOT, "dist", "digipay-tejarat-brochure.pdf");
await page.pdf({ path: out, width: "297mm", height: "210mm", printBackground: true, preferCSSPageSize: true });
if (process.argv.includes("--png")) {
  mkdirSync(path.join(ROOT, "dist/preview"), { recursive: true });
  await page.setViewportSize({ width: 1123, height: 794 });
  const els = await page.$$("section.page");
  for (let i = 0; i < els.length; i++) await els[i].screenshot({ path: path.join(ROOT, `dist/preview/p${String(i + 1).padStart(2, "0")}.png`) });
}
await browser.close();
console.log("pdf:", out);
