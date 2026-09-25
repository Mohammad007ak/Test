import { useEffect, useMemo, useRef, useState } from "react";

// A crowd of little people with coin heads. Move the mouse over it, or hold
// a finger on it, and they walk over and gather round; move away or let go
// and they wander back. Drawn on a canvas; idle when nothing moves or it's off screen.

const HINT_KEY = "dg:crowd-hint-seen";
const INK = "#111126";

// One figure, drawn once as line art: a tilted white coin for a head with
// its ridged rim showing, a soft white body with the arms in front, and a
// shadow. viewBox 100×150; the feet stand at y 141. `pose` is "stand", or
// "a" / "b" for the two steps of the walk (stride, then passing).
function figureSvg(pose) {
  // Coin: face ellipse, rim = same ellipse shifted left; both tilted.
  const [cx, cy, rx, ry, shift] = [56, 45, 29, 32, 12];
  const ridges = [];
  for (let a = 98; a <= 262; a += 13) {
    const t = (a * Math.PI) / 180;
    const x = Math.cos(t) * rx;
    const y = Math.sin(t) * ry;
    ridges.push(`M${(cx + x).toFixed(1)} ${(cy + y).toFixed(1)}L${(cx - shift + x).toFixed(1)} ${(cy + y).toFixed(1)}`);
  }
  const P = {
    stand: { l: 0, r: 0, al: 0, ar: 0, lean: 0 },
    a: { l: 24, r: -24, al: 34, ar: -30, lean: 4 },
    b: { l: 6, r: -4, al: 8, ar: -6, lean: 2 },
  }[pose];
  const leg = (x, turn) =>
    `<path transform="rotate(${turn} ${x + 6} 108)" d="M${x} 104 L${x + 0.5} 134 C${x + 0.5} 140 ${x + 12} 140 ${x + 12} 134 L${x + 12} 104 Z" fill="#fff"/>`;
  const armL = `<path transform="rotate(${P.al} 39 83)" d="M40 81 C33 85 31 95 32 106 C32 111 38 111 38 106 C38 99 39 93 41 89" fill="#fff"/>`;
  const armR = `<path transform="rotate(${P.ar} 63 83)" d="M62 81 C69 85 71 95 70 106 C70 111 64 111 64 106 C64 99 63 93 61 89" fill="#fff"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 150">
<ellipse cx="51" cy="141" rx="21" ry="5.5" fill="${INK}"/>
<g stroke="${INK}" stroke-width="4.5" stroke-linejoin="round" stroke-linecap="round" transform="rotate(${P.lean} 51 141)">
${leg(39, P.l)}${leg(51, P.r)}
<path d="M46 73 C40 75 38 84 38 94 L37 108 C37 114 42 117 51 117 C60 117 65 114 65 108 L64 94 C64 84 62 75 56 73 Z" fill="#fff"/>
<path d="M51 109 L51 116" stroke-width="3"/>
${armL}${armR}
<g transform="rotate(-10 ${cx} ${cy})">
<ellipse cx="${cx - shift}" cy="${cy}" rx="${rx}" ry="${ry}" fill="#fff"/>
<path d="M${cx - shift} ${cy - ry} L${cx} ${cy - ry} M${cx - shift} ${cy + ry} L${cx} ${cy + ry}"/>
<path d="${ridges.join("")}" stroke-width="3.6"/>
<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="#fff"/>
</g>
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
  // The sprite's feet sit at 141/150 of its height.
  ctx.drawImage(sprites[pose], -w / 2, -h * (141 / 150), w, h);
  ctx.restore();
}

export default function CoinCrowd({ title, text }) {
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
  }, []);

  return (
    <div className="crowd" ref={wrap}>
      <canvas ref={canvas} aria-hidden="true" />
      <div className="crowd-text" ref={textBox}>
        <strong>{title}</strong>
        {text && <span>{text}</span>}
        {hint && (
          <span className="crowd-hint">{hover ? "موس را روی این‌جا ببرید" : "انگشتتان را جایی نگه دارید 👆"}</span>
        )}
      </div>
    </div>
  );
}
