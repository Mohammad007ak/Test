import { useEffect, useMemo, useRef, useState } from "react";
import { INK, figureSvg } from "./Figure.jsx";

// A crowd of little people with coin heads. Move the mouse over it, or hold
// a finger on it, and they walk over and gather round; move away or let go
// and they wander back. Drawn on a canvas; idle when nothing moves or it's off screen.

const HINT_KEY = "dg:crowd-hint-seen";

// The kinds of figure in a crowd: an ordinary member (calm or angry), Digi
// Gharz itself, or the member looking at the screen (calm, or worried when
// their own installment is unpaid).
const KINDS = {
  plain: {},
  logo: { logo: true },
  angry: { angry: true },
  me: { me: true },
  worried: { me: true, worried: true },
};
const isMe = (kind) => kind === "me" || kind === "worried";

// Rasterize each kind in each pose once, sharp for this screen, then just
// stamp them.
async function makeSprites(px) {
  const out = {};
  for (const [kind, opts] of Object.entries(KINDS))
    for (const pose of ["stand", "a", "b"]) {
      const img = new Image();
      img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(figureSvg(pose, opts))}`;
      await img.decode();
      const c = document.createElement("canvas");
      c.width = Math.round(px * (120 / 160));
      c.height = Math.round(px);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      out[`${kind}:${pose}`] = c;
    }
  return out;
}

// `count` people of the kinds in `cast` (plain when it doesn't say): `done`
// of them wear a check mark (Digi Gharz first, as it's always paid first,
// the member themself if `meDone`, the rest at random), and seats past
// `present` are still empty, drawn faded. When `angry`, the others are cross
// and the member is worried.
function makePeople(width, height, base, floor, count, done, present, cast, angry, meDone) {
  const kind = (i) => {
    const k = cast?.[i] ?? "plain";
    if (!angry) return k;
    return k === "plain" ? "angry" : k === "me" ? "worried" : k;
  };
  const order = Array.from({ length: count }, (_, i) => i).sort(() => Math.random() - 0.5);
  order.sort((a, b) => (kind(b) === "logo") - (kind(a) === "logo"));
  const mine = order.filter((i) => isMe(kind(i)));
  const others = order.filter((i) => !isMe(kind(i)));
  const checked = new Set(meDone && mine.length ? [...mine, ...others.slice(0, done - 1)] : others.slice(0, done));
  // Feet no higher than `floor`, so heads stay clear of the banner's text.
  const top = Math.max(height * 0.5, floor);
  const bottom = height - 6; // everyone fully in view, so they can be counted
  const few = count <= 3; // a small group stands together, side by side
  return Array.from({ length: count }, (_, i) => {
    const edge = base * 0.35;
    const x = few
      ? width / 2 + (i - (count - 1) / 2) * base * 0.75
      : isMe(kind(i))
        ? width * 0.42 // front and centre (a little off the middle, clear of the text)
        : edge + ((i + 0.5) / count) * (width - 2 * edge) + (Math.random() - 0.5) * base * 0.3;
    const front = isMe(kind(i)) && !few; // the member stands in the front row
    const y = few ? bottom - base * 0.1 : front ? bottom - base * 0.08 : top + Math.random() * (bottom - top);
    return {
      homeX: x,
      homeY: y,
      x,
      y,
      vx: 0,
      vy: 0,
      size: (0.78 + ((y - top) / (bottom - top)) * 0.3) * (isMe(kind(i)) ? 1.1 : 1), // nearer is bigger
      speed: 0.7 + Math.random() * 0.6,
      phase: Math.random() * Math.PI * 2,
      facing: Math.random() < 0.5 ? -1 : 1,
      kind: kind(i),
      me: isMe(kind(i)),
      checked: checked.has(i),
      empty: i < count - present, // the ones who came fill in from the right (RTL)
      slot: 0,
    };
  });
}

function drawPerson(ctx, sprites, base, p, t) {
  const moving = Math.hypot(p.vx, p.vy);
  if (p.vx > 0.4) p.facing = 1;
  else if (p.vx < -0.4) p.facing = -1;
  const h = base * p.size;
  const w = h * (120 / 160);
  let pose = moving < 0.35 ? "stand" : Math.sin(p.phase) > 0 ? "a" : "b";
  let bob = moving < 0.35 ? 0 : Math.abs(Math.sin(p.phase)) * h * 0.035;
  let shake = 0;
  // Standing and angry: stamping a foot and trembling, each in their own time.
  if (p.kind === "angry" && moving < 0.35) {
    const stamp = Math.sin(t * 0.011 + p.phase);
    pose = stamp > 0.35 ? "a" : "stand";
    bob = Math.max(0, stamp) * h * 0.05;
    shake = Math.sin(t * 0.06 + p.phase * 3) * h * 0.012;
  }
  // Worried: a nervous shiver, and a flinch when a tomato lands.
  if (p.kind === "worried") {
    shake = Math.sin(t * 0.09 + p.phase) * h * 0.008;
    const hit = p.hitT ? (t - p.hitT) / 380 : 1;
    if (hit < 1) {
      shake += Math.sin(hit * 30) * h * 0.05 * (1 - hit);
      bob = -h * 0.03 * (1 - hit);
      pose = "b";
    }
  }
  // Winding up and throwing.
  if (p.throwT && t - p.throwT < 320) {
    pose = "a";
    bob = Math.sin(((t - p.throwT) / 320) * Math.PI) * h * 0.09;
  }
  ctx.save();
  if (p.empty) ctx.globalAlpha = 0.3;
  ctx.translate(p.x + shake, p.y - bob);
  ctx.scale(p.facing, 1);
  // The sprite's feet sit at 150/160 of its height.
  ctx.drawImage(sprites[`${p.kind}:${pose}`], -w / 2, -h * (150 / 160), w, h);
  ctx.restore();
  const headTop = p.y - bob - h * (136 / 160);
  if (p.me) drawYou(ctx, p.x + shake, headTop, h, p.checked);
  else if (p.checked) drawCheck(ctx, p.x, headTop, h);
}

// A little "you" tag with a pointer over the member's own head (green, with
// a check, once they've been paid).
function drawYou(ctx, x, headTop, h, paid) {
  const fs = Math.max(11, h * 0.13);
  const label = paid ? "✓ شما" : "شما";
  ctx.save();
  ctx.font = `800 ${fs}px "Estedad Variable", "Vazirmatn Variable", Tahoma, sans-serif`;
  ctx.direction = "rtl";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const w = ctx.measureText(label).width + fs * 1.1;
  const ph = fs * 1.6;
  const y = headTop - ph / 2 - h * 0.08;
  ctx.lineWidth = Math.max(1.5, h * 0.022);
  ctx.lineJoin = "round";
  ctx.strokeStyle = INK;
  ctx.fillStyle = paid ? "#3ddc84" : "#fff";
  ctx.beginPath();
  ctx.roundRect(x - w / 2, y - ph / 2, w, ph, ph / 2);
  ctx.moveTo(x - fs * 0.35, y + ph / 2);
  ctx.lineTo(x, y + ph / 2 + fs * 0.45);
  ctx.lineTo(x + fs * 0.35, y + ph / 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = INK;
  ctx.fillText(label, x, y + fs * 0.06);
  ctx.restore();
}

// A tomato in flight: red, an ink outline, a shine and a green top.
function drawTomato(ctx, r) {
  ctx.fillStyle = "#ff4b3e";
  ctx.beginPath();
  ctx.ellipse(0, 0, r * 1.08, r, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "rgb(255 255 255 / 0.75)";
  ctx.beginPath();
  ctx.ellipse(-r * 0.4, -r * 0.2, r * 0.22, r * 0.13, -0.6, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#3ddc84";
  ctx.beginPath();
  for (let k = 0; k < 10; k++) {
    const a = (k / 10) * Math.PI * 2 - Math.PI / 2;
    const rr = k % 2 ? r * 0.18 : r * 0.55;
    ctx.lineTo(Math.cos(a) * rr, -r * 0.8 + Math.sin(a) * rr * 0.6);
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
}

// An egg in flight: a cream oval with a shine and a few speckles.
function drawEgg(ctx, r) {
  ctx.fillStyle = "#fff6e4";
  ctx.beginPath();
  ctx.ellipse(0, r * 0.05, r * 0.8, r * 1.05, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "rgb(255 255 255 / 0.9)";
  ctx.beginPath();
  ctx.ellipse(-r * 0.3, -r * 0.35, r * 0.16, r * 0.26, -0.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#d9b98a";
  for (const [x, y] of [
    [0.3, 0.1],
    [-0.15, 0.45],
    [0.2, 0.6],
  ]) {
    ctx.beginPath();
    ctx.arc(x * r, y * r, r * 0.06, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawMissile(ctx, m, r) {
  ctx.save();
  ctx.translate(m.x, m.y);
  ctx.rotate(m.spin);
  ctx.lineWidth = Math.max(1.5, r * 0.2);
  ctx.lineJoin = "round";
  ctx.strokeStyle = INK;
  (m.egg ? drawEgg : drawTomato)(ctx, r);
  ctx.restore();
}

const easeOutBack = (k) => 1 + 2.7 * (k - 1) ** 3 + 1.7 * (k - 1) ** 2;

// What's left on the member's face: it pops out flat on impact, then slides
// and drips down and fades. A tomato leaves red pulp and seeds; an egg, the
// white with its yolk, which slowly runs.
function drawSplat(ctx, x, y, r, s, t) {
  const age = t - s.t;
  const pop = Math.min(1, age / 140);
  const grow = 0.35 + 0.65 * easeOutBack(pop);
  const flat = 1 - pop;
  const run = Math.min(1, age / 1600);
  ctx.save();
  ctx.globalAlpha = age < 1300 ? 1 : Math.max(0, 1 - (age - 1300) / 700);
  ctx.translate(x, y + r * 0.35 * run);
  ctx.lineWidth = Math.max(1.5, r * 0.12);
  ctx.lineJoin = "round";
  ctx.strokeStyle = INK;
  // Drips first, so the blob's outline sits over their tops.
  ctx.fillStyle = s.egg ? "#fff6e4" : "#ff5b45";
  for (const d of s.drips) {
    const len = r * (0.3 + d.len * run * 1.3);
    const w = r * 0.13;
    ctx.beginPath();
    ctx.roundRect(d.x * r - w, r * 0.2, w * 2, len, w);
    ctx.arc(d.x * r, r * 0.2 + len, w * 1.35, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.save();
  ctx.rotate(s.rot);
  ctx.scale(grow * (1 + 0.35 * flat), grow * (1 - 0.3 * flat));
  const blob = (scale) => {
    ctx.beginPath();
    s.lobes.forEach((k, i) => {
      const a = (i / s.lobes.length) * Math.PI * 2;
      const b = ((i + 0.5) / s.lobes.length) * Math.PI * 2;
      const rr = r * k * scale;
      ctx.quadraticCurveTo(
        Math.cos(a) * rr * 1.15,
        Math.sin(a) * rr * 1.15,
        Math.cos(b) * rr * 0.8,
        Math.sin(b) * rr * 0.8,
      );
    });
    ctx.closePath();
  };
  ctx.fillStyle = s.egg ? "#fffdf6" : "#ff5b45";
  blob(1);
  ctx.fill();
  ctx.stroke();
  if (s.egg) {
    ctx.restore();
    // The yolk, sliding down a little faster than the white.
    const yx = s.yolk.x * r;
    const yy = s.yolk.y * r + r * 0.3 * run;
    ctx.fillStyle = "#ffc53d";
    ctx.beginPath();
    ctx.roundRect(yx - r * 0.12, yy, r * 0.24, r * (0.1 + 0.9 * run), r * 0.12);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(yx, yy, r * 0.42 * grow, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "rgb(255 255 255 / 0.85)";
    ctx.beginPath();
    ctx.ellipse(yx - r * 0.14, yy - r * 0.14, r * 0.1, r * 0.06, -0.6, 0, Math.PI * 2);
    ctx.fill();
  } else {
    ctx.fillStyle = "#ff8a73";
    blob(0.55);
    ctx.fill();
    ctx.fillStyle = "#ffe08a";
    for (const d of s.seeds) {
      ctx.beginPath();
      ctx.ellipse(d.x * r, d.y * r, r * 0.11, r * 0.065, d.a, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }
  ctx.restore();
}

// Bits thrown off by the impact: drops of pulp, or shell and yolk.
function drawBit(ctx, b, r, t) {
  const dt = t - b.t;
  const x = b.x + b.vx * dt;
  const y = b.y + b.vy * dt + 0.5 * b.g * dt * dt;
  ctx.save();
  ctx.globalAlpha = Math.max(0, 1 - dt / b.life);
  ctx.translate(x, y);
  ctx.rotate(b.rot + b.vr * dt);
  ctx.lineWidth = Math.max(1, r * 0.09);
  ctx.lineJoin = "round";
  ctx.strokeStyle = INK;
  ctx.fillStyle = b.color;
  ctx.beginPath();
  if (b.shell) {
    ctx.moveTo(-r * 0.3 * b.size, -r * 0.2 * b.size);
    ctx.lineTo(r * 0.28 * b.size, -r * 0.26 * b.size);
    ctx.lineTo(r * 0.05 * b.size, r * 0.3 * b.size);
    ctx.closePath();
  } else ctx.arc(0, 0, r * 0.2 * b.size, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

// A comic-book sound word by the impact.
function drawWord(ctx, w, r, t) {
  const dt = t - w.t;
  const k = Math.min(1, dt / 120);
  ctx.save();
  ctx.globalAlpha = dt < 520 ? 1 : Math.max(0, 1 - (dt - 520) / 200);
  ctx.translate(w.x, w.y - r * 0.9 * Math.min(1, dt / 720));
  ctx.rotate(w.rot);
  ctx.scale(easeOutBack(k), easeOutBack(k));
  ctx.font = `900 ${r * 1.9}px "Estedad Variable", "Vazirmatn Variable", Tahoma, sans-serif`;
  ctx.direction = "rtl";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";
  ctx.lineWidth = r * 0.45;
  ctx.strokeStyle = INK;
  ctx.strokeText(w.text, 0, 0);
  ctx.fillStyle = w.color;
  ctx.fillText(w.text, 0, 0);
  ctx.restore();
}

// A green badge with a check, floating over the head of someone who has
// already been paid their loan.
function drawCheck(ctx, x, headTop, h) {
  const r = h * 0.1;
  const y = headTop - r - h * 0.03;
  ctx.save();
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.fillStyle = "#3ddc84";
  ctx.strokeStyle = INK;
  ctx.lineWidth = Math.max(1.5, h * 0.028);
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.lineWidth = Math.max(2, h * 0.034);
  ctx.beginPath();
  ctx.moveTo(x - r * 0.45, y + r * 0.02);
  ctx.lineTo(x - r * 0.1, y + r * 0.38);
  ctx.lineTo(x + r * 0.5, y - r * 0.35);
  ctx.stroke();
  ctx.restore();
}

// `count` is how many people to show (the member's plan size), `done` how
// many of them have already received their loan, and `present` how many
// seats are taken while the group is still filling up. `cast` names each
// figure's kind ("plain" or "logo"), by position. `angry` turns the banner
// red and the crowd cross (an installment is unpaid), `pelting` has them
// throw tomatoes and eggs at the member (it's overdue); `action` is a button
// shown under the text.
export default function CoinCrowd({
  title,
  text,
  count = 12,
  done = 0,
  present = count,
  cast,
  angry = false,
  meDone = false,
  pelting = false,
  action,
  children,
}) {
  const castKey = cast?.join(",") ?? "";
  const wrap = useRef(null);
  const canvas = useRef(null);
  const textBox = useRef(null);
  const hover = useMemo(() => window.matchMedia("(hover: hover) and (pointer: fine)").matches, []);
  const [hint, setHint] = useState(() => {
    try {
      return !localStorage.getItem(HINT_KEY);
    } catch {
      return true;
    }
  });

  useEffect(() => {
    const el = canvas.current;
    const box = wrap.current;
    const ctx = el.getContext("2d");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = 0;
    let height = 0;
    let people = [];
    let sprites = null;
    let base = 80; // a full-size figure's height, px
    let floor = 0; // highest the feet may stand: just below the text
    let frame = 0;
    let alive = true;
    let visible = true;
    const pointer = { down: false, x: 0, y: 0 };
    // Once the member's installment is overdue, every few seconds one of the
    // cross members lobs a tomato (now and then an egg) at them.
    let missiles = [];
    let splats = [];
    let bits = [];
    let words = [];
    let nextThrow = 0;

    const resize = () => {
      const rect = box.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      el.width = Math.round(width * dpr);
      el.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      base = Math.max(64, Math.min(210, height * 0.34)); // bigger on a full-screen banner
      // The hint may sit over the crowd's heads; only the title and subtitle can't.
      const hintEl = textBox.current.querySelector(".crowd-hint");
      const textEnd = hintEl ? hintEl.offsetTop : textBox.current.offsetHeight;
      floor = textBox.current.offsetTop + textEnd + 8 + base * 1.2; // room for a check mark too
      people = makePeople(width, height, base, floor, count, Math.min(done, count), present, cast, angry, meDone);
      missiles = [];
      splats = [];
      bits = [];
      words = [];
      makeSprites(base * 1.1 * dpr).then((made) => {
        if (!alive) return;
        sprites = made;
        draw();
        wake();
      });
    };

    const draw = (t = performance.now()) => {
      ctx.clearRect(0, 0, width, height);
      if (!sprites) return;
      // Nearer (lower) people are drawn last so they overlap the ones behind;
      // the member always in front.
      for (const p of [...people].sort((a, b) => a.me - b.me || a.y - b.y)) drawPerson(ctx, sprites, base, p, t);
      const r = base * 0.12;
      for (const s of splats) {
        const h = base * s.who.size;
        drawSplat(ctx, s.who.x + s.ox * h, s.who.y - h * 0.72 + s.oy * h, r * 1.8, s, t);
      }
      for (const b of bits) drawBit(ctx, b, r, t);
      for (const m of missiles) drawMissile(ctx, m, r);
      for (const w of words) drawWord(ctx, w, r, t);
    };

    const splat = (me, egg, x, y, t) => {
      const rnd = (a, b) => a + Math.random() * (b - a);
      me.hitT = t;
      splats.push({
        who: me,
        egg,
        t,
        ox: rnd(-0.1, 0.1),
        oy: rnd(-0.06, 0.06),
        rot: rnd(0, Math.PI),
        lobes: Array.from({ length: egg ? 9 : 11 }, (_, i) => (i % 2 ? 0.7 : 0.95) + rnd(0, egg ? 0.45 : 0.3)),
        drips: Array.from({ length: egg ? 2 : 3 }, () => ({ x: rnd(-0.6, 0.6), len: rnd(0.3, 1) })),
        seeds: Array.from({ length: 6 }, () => ({ x: rnd(-0.7, 0.7), y: rnd(-0.6, 0.6), a: rnd(0, Math.PI) })),
        yolk: { x: rnd(-0.25, 0.25), y: rnd(-0.2, 0.1) },
      });
      // Bits fly off, up and out, then fall.
      const speed = base * 0.0028;
      const g = base * 0.000014;
      const n = egg ? 9 : 10;
      for (let i = 0; i < n; i++) {
        const a = -Math.PI / 2 + rnd(-1.4, 1.4);
        const v = speed * rnd(0.5, 1.2);
        const shell = egg && i < 5;
        bits.push({
          t,
          x,
          y,
          vx: Math.cos(a) * v,
          vy: Math.sin(a) * v,
          g,
          rot: rnd(0, 6),
          vr: rnd(-0.02, 0.02),
          size: rnd(0.6, 1.2),
          life: rnd(450, 700),
          shell,
          color: shell ? "#fff6e4" : egg ? "#ffc53d" : "#ff4b3e",
        });
      }
      words.push({
        t,
        x: x + (x < width / 2 ? 1 : -1) * base * 0.55,
        y: y - base * 0.2,
        rot: rnd(-0.25, 0.25),
        text: egg ? "ترق!" : "شلپ!",
        color: egg ? "#ffc53d" : "#fff",
      });
    };

    const pelt = (t) => {
      const me = people.find((p) => p.me && !p.empty);
      const throwers = people.filter((p) => p.kind === "angry" && !p.empty);
      if (!me || !throwers.length) return;
      if (!nextThrow) nextThrow = t + 1400;
      if (t >= nextThrow) {
        const from = throwers[Math.floor(Math.random() * throwers.length)];
        const h = base * from.size;
        from.throwT = t;
        from.facing = me.x > from.x ? 1 : -1;
        const dist = Math.hypot(me.x - from.x, me.y - from.y);
        missiles.push({
          egg: Math.random() < 0.3,
          x0: from.x + from.facing * h * 0.25,
          y0: from.y - h * 0.62,
          t0: t,
          dur: 520 + dist * 0.9,
          dir: from.facing,
        });
        nextThrow = t + 2400 + Math.random() * 1800;
      }
      const h = base * me.size;
      // Head for where the member's head is now, even if they've moved.
      const tx = me.x;
      const ty = me.y - h * 0.8;
      missiles = missiles.filter((m) => {
        const k = (t - m.t0) / m.dur;
        if (k >= 1) {
          splat(me, m.egg, tx, ty, t);
          return false;
        }
        m.x = m.x0 + (tx - m.x0) * k;
        m.y = m.y0 + (ty - m.y0) * k - base * 0.9 * 4 * k * (1 - k);
        m.spin = k * Math.PI * (m.egg ? 2 : 3) * m.dir;
        return true;
      });
      splats = splats.filter((s) => t - s.t < 2000);
      bits = bits.filter((b) => t - b.t < b.life);
      words = words.filter((w) => t - w.t < 720);
    };

    const tick = (t) => {
      frame = 0;
      let busy = pointer.down || angry; // an angry crowd never quite settles
      for (const p of people) {
        let tx = p.homeX;
        let ty = p.homeY;
        if (pointer.down && angry) {
          // Angry: they back away from the finger, out of its reach, and
          // stay inside the banner.
          const fx = p.homeX - pointer.x;
          const fy = (p.homeY - (pointer.y + base * 0.45)) * 1.6;
          const d = Math.hypot(fx, fy) || 1;
          const reach = base * 1.6;
          if (d < reach) {
            tx = Math.min(width - base * 0.3, Math.max(base * 0.3, pointer.x + (fx / d) * reach));
            ty = Math.min(height - 6, Math.max(floor, p.homeY + ((fy / d) * (reach - d)) / 1.6));
          }
        } else if (pointer.down) {
          // Rings around the finger (golden angle: an even, tight cluster),
          // feet a little below it so the heads crowd round the touch.
          const ring = base * (0.12 + 0.2 * Math.sqrt(p.slot));
          const angle = p.slot * 2.39996;
          tx = Math.min(width - base * 0.3, Math.max(base * 0.3, pointer.x + Math.cos(angle) * ring));
          ty = Math.max(floor, pointer.y + base * 0.45 + Math.sin(angle) * ring * 0.55);
        }
        const dx = tx - p.x;
        const dy = ty - p.y;
        const pull = (pointer.down ? 0.008 : 0.004) * p.speed;
        // Keep a little personal space so the crowd doesn't pile up.
        const space = base * 0.26;
        let push = 0;
        let pushY = 0;
        for (const q of people) {
          if (q === p) continue;
          const ox = p.x - q.x;
          const oy = (p.y - q.y) * 1.6;
          const d = Math.hypot(ox, oy);
          // Everyone keeps clear of the member, so they're easy to spot.
          const room = p.me || q.me ? space * 2.2 : space;
          if (d > 0 && d < room) {
            push += (ox / d) * (room - d) * 0.05;
            pushY += (oy / d) * (room - d) * 0.03;
          }
        }
        p.vx = (p.vx + dx * pull + push) * 0.86;
        p.vy = (p.vy + dy * pull + pushY) * 0.86;
        const cap = base * 0.03 * p.speed; // an unhurried walk
        const v = Math.hypot(p.vx, p.vy);
        if (v > cap) {
          p.vx *= cap / v;
          p.vy *= cap / v;
        }
        p.x += p.vx;
        p.y += p.vy;
        p.phase += v * 0.2;
        if (v > 0.05) busy = true; // settled: stop drawing until the next touch
      }
      if (angry && pelting) pelt(t);
      draw(t);
      if (busy && visible) frame = requestAnimationFrame(tick);
    };

    const wake = () => {
      if (!still && visible && !frame) frame = requestAnimationFrame(tick);
    };

    const at = (e) => {
      const rect = el.getBoundingClientRect();
      pointer.x = e.clientX - rect.left;
      pointer.y = e.clientY - rect.top;
    };
    // The crowd follows the mouse as soon as it's over the banner; on a touch
    // screen, a finger held down.
    const gather = (e) => {
      at(e);
      if (pointer.down) return wake();
      pointer.down = true;
      // Everyone gets a place in rings around the pointer, nearest first.
      people
        .map((p) => [p, Math.hypot(p.x - pointer.x, p.y - pointer.y)])
        .sort((a, b) => a[1] - b[1])
        .forEach(([p], rank) => (p.slot = rank));
      setHint(false);
      try {
        localStorage.setItem(HINT_KEY, "1");
      } catch {
        // Private mode: the hint just shows again next time.
      }
      wake();
    };
    const down = (e) => {
      if (e.button > 0) return;
      if (e.pointerType !== "mouse") el.setPointerCapture?.(e.pointerId);
      gather(e);
    };
    const move = (e) => {
      if (e.pointerType === "mouse" || pointer.down) gather(e);
    };
    const up = (e) => {
      if (e.pointerType === "mouse") return; // still hovering: keep following
      pointer.down = false;
      wake();
    };
    const leave = (e) => {
      if (e.pointerType !== "mouse") return;
      pointer.down = false;
      wake();
    };
    const noMenu = (e) => e.preventDefault();

    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    el.addEventListener("lostpointercapture", up);
    el.addEventListener("pointerleave", leave);
    el.addEventListener("contextmenu", noMenu);

    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting && !document.hidden;
      if (visible) wake();
    });
    observer.observe(box);
    const onVisibility = () => {
      visible = !document.hidden;
      if (visible) wake();
    };
    document.addEventListener("visibilitychange", onVisibility);
    const sizer = new ResizeObserver(resize);
    sizer.observe(box);

    return () => {
      alive = false;
      cancelAnimationFrame(frame);
      observer.disconnect();
      sizer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
      el.removeEventListener("lostpointercapture", up);
      el.removeEventListener("pointerleave", leave);
      el.removeEventListener("contextmenu", noMenu);
    };
    // `cast` is compared by its contents (castKey), not the array's identity.
  }, [count, done, present, castKey, angry, meDone, pelting]);

  return (
    <div className={`crowd ${angry ? "angry" : ""}`} ref={wrap}>
      <canvas ref={canvas} aria-hidden="true" />
      <div className="crowd-text" ref={textBox}>
        {children}
        <strong>{title}</strong>
        {text && <span>{text}</span>}
        {action}
        {hint && !action && count > 0 && (
          <span className="crowd-hint">{hover ? "موس را روی این‌جا ببرید" : "انگشتتان را جایی نگه دارید 👆"}</span>
        )}
      </div>
    </div>
  );
}
