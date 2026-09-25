import { useEffect, useRef, useState } from "react";

// A crowd of little people with coin heads. Press and hold anywhere on it
// (mouse or finger) and they walk over and gather round; let go and they
// wander back. Drawn on a canvas; idle when nothing moves or it's off screen.

const HINT_KEY = "dg:crowd-hint-seen";
const INK = "#15152b";

// One figure, drawn once as line art: a white coin for a head (its ridged
// edge showing on the right), a small white body, stubby legs and a shadow.
// viewBox 100×150; the feet stand at y 140. `legs` picks the walk pose.
function figureSvg(legs) {
  const ridges = [];
  for (let a = -78; a <= 78; a += 13) {
    const r = (a * Math.PI) / 180;
    const c = Math.cos(r) * 33;
    const d = Math.sin(r) * 33;
    ridges.push(`M${(49 + c).toFixed(1)} ${(46 + d).toFixed(1)}L${(59 + c).toFixed(1)} ${(46 + d).toFixed(1)}`);
  }
  const leg = (x, turn) =>
    `<path transform="rotate(${turn} ${x + 5} 112)" d="M${x} 108v24a5 5 0 0 0 10 0v-24z" fill="#fff"/>`;
  const [l, r] = { stand: [0, 0], a: [16, -12], b: [-12, 16] }[legs];
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 150">
<g stroke="${INK}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round">
<ellipse cx="50" cy="141" rx="23" ry="5" fill="${INK}" stroke="none"/>
${leg(36, l)}${leg(54, r)}
<path d="M30 118V92c0-10 8-16 20-16s20 6 20 16v26c0 4-3 6-6 6H36c-3 0-6-2-6-6z" fill="#fff"/>
<path d="M36 94c-3 8-3 16 0 22M64 94c3 8 3 16 0 22" fill="none" stroke-width="3"/>
<circle cx="59" cy="46" r="33" fill="#fff"/>
<path d="${ridges.join("")}" stroke-width="3"/>
<circle cx="49" cy="46" r="33" fill="#fff"/>
</g></svg>`;
}

// Rasterize each pose once, sharp for this screen, then just stamp them.
async function makeSprites(px) {
  const out = {};
  for (const pose of ["stand", "a", "b"]) {
    const img = new Image();
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(figureSvg(pose))}`;
    await img.decode();
    const c = document.createElement("canvas");
    c.width = Math.round(px * (100 / 150));
    c.height = Math.round(px);
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    out[pose] = c;
  }
  return out;
}

function makePeople(width, height, base, floor) {
  const count = Math.max(16, Math.min(70, Math.round(width / (base * 0.2))));
  // Feet no higher than `floor`, so heads stay clear of the banner's text.
  const top = Math.max(height * 0.5, floor);
  const bottom = height + base * 0.3; // the front row is cut off, like a crowd
  return Array.from({ length: count }, (_, i) => {
    const x = ((i + 0.5) / count) * width + (Math.random() - 0.5) * base * 0.4;
    const y = top + Math.random() * (bottom - top);
    return {
      homeX: x,
      homeY: y,
      x,
      y,
      vx: 0,
      vy: 0,
      size: 0.78 + ((y - top) / (bottom - top)) * 0.3, // nearer is bigger
      speed: 0.7 + Math.random() * 0.6,
      phase: Math.random() * Math.PI * 2,
      facing: Math.random() < 0.5 ? -1 : 1,
      slot: 0,
    };
  });
}

function drawPerson(ctx, sprites, base, p) {
  const moving = Math.hypot(p.vx, p.vy);
  if (p.vx > 0.4) p.facing = 1;
  else if (p.vx < -0.4) p.facing = -1;
  const pose = moving < 0.35 ? "stand" : Math.sin(p.phase) > 0 ? "a" : "b";
  const h = base * p.size;
  const w = h * (100 / 150);
  const bob = moving < 0.35 ? 0 : Math.abs(Math.sin(p.phase)) * h * 0.035;
  ctx.save();
  ctx.translate(p.x, p.y - bob);
  ctx.scale(p.facing, 1);
  // The sprite's feet sit at 140/150 of its height.
  ctx.drawImage(sprites[pose], -w / 2, -h * (140 / 150), w, h);
  ctx.restore();
}

export default function CoinCrowd({ title, text }) {
  const wrap = useRef(null);
  const canvas = useRef(null);
  const textBox = useRef(null);
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

    const resize = () => {
      const rect = box.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      el.width = Math.round(width * dpr);
      el.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      base = Math.max(64, Math.min(120, height * 0.34));
      // The hint may sit over the crowd's heads; only the title and subtitle can't.
      const hintEl = textBox.current.querySelector(".crowd-hint");
      const textEnd = hintEl ? hintEl.offsetTop : textBox.current.offsetHeight;
      floor = textBox.current.offsetTop + textEnd + 8 + base * 1.05;
      people = makePeople(width, height, base, floor);
      makeSprites(base * 1.1 * dpr).then((made) => {
        if (!alive) return;
        sprites = made;
        draw();
      });
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      if (!sprites) return;
      // Nearer (lower) people are drawn last so they overlap the ones behind.
      for (const p of [...people].sort((a, b) => a.y - b.y)) drawPerson(ctx, sprites, base, p);
    };

    const tick = () => {
      frame = 0;
      let busy = pointer.down;
      for (const p of people) {
        let tx = p.homeX;
        let ty = p.homeY;
        if (pointer.down) {
          // Rings around the finger (golden angle: an even, tight cluster),
          // feet a little below it so the heads crowd round the touch.
          const ring = base * (0.12 + 0.2 * Math.sqrt(p.slot));
          const angle = p.slot * 2.39996;
          tx = Math.min(width - base * 0.3, Math.max(base * 0.3, pointer.x + Math.cos(angle) * ring));
          ty = Math.max(floor, pointer.y + base * 0.45 + Math.sin(angle) * ring * 0.55);
        }
        const dx = tx - p.x;
        const dy = ty - p.y;
        const pull = (pointer.down ? 0.012 : 0.006) * p.speed;
        // Keep a little personal space so the crowd doesn't pile up.
        const space = base * 0.26;
        let push = 0;
        let pushY = 0;
        for (const q of people) {
          if (q === p) continue;
          const ox = p.x - q.x;
          const oy = (p.y - q.y) * 1.6;
          const d = Math.hypot(ox, oy);
          if (d > 0 && d < space) {
            push += (ox / d) * (space - d) * 0.05;
            pushY += (oy / d) * (space - d) * 0.03;
          }
        }
        p.vx = (p.vx + dx * pull + push) * 0.86;
        p.vy = (p.vy + dy * pull + pushY) * 0.86;
        const cap = base * 0.055 * p.speed;
        const v = Math.hypot(p.vx, p.vy);
        if (v > cap) {
          p.vx *= cap / v;
          p.vy *= cap / v;
        }
        p.x += p.vx;
        p.y += p.vy;
        p.phase += v * 0.16;
        if (v > 0.05) busy = true; // settled: stop drawing until the next touch
      }
      draw();
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
    const down = (e) => {
      if (e.button > 0) return;
      at(e);
      pointer.down = true;
      // Everyone gets a place in rings around the finger, nearest first.
      people
        .map((p) => [p, Math.hypot(p.x - pointer.x, p.y - pointer.y)])
        .sort((a, b) => a[1] - b[1])
        .forEach(([p], rank) => (p.slot = rank));
      el.setPointerCapture?.(e.pointerId);
      setHint(false);
      try {
        localStorage.setItem(HINT_KEY, "1");
      } catch {
        // Private mode: the hint just shows again next time.
      }
      if (still) return;
      wake();
    };
    const move = (e) => {
      if (!pointer.down) return;
      at(e);
      wake();
    };
    const up = () => {
      pointer.down = false;
      wake();
    };
    const noMenu = (e) => e.preventDefault();

    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    el.addEventListener("lostpointercapture", up);
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
      el.removeEventListener("contextmenu", noMenu);
    };
  }, []);

  return (
    <div className="crowd" ref={wrap}>
      <canvas ref={canvas} aria-hidden="true" />
      <div className="crowd-text" ref={textBox}>
        <strong>{title}</strong>
        {text && <span>{text}</span>}
        {hint && <span className="crowd-hint">انگشتتان را جایی نگه دارید 👆</span>}
      </div>
    </div>
  );
}
