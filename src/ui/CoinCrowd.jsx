import { useEffect, useMemo, useRef, useState } from "react";

// A crowd of little people with coin heads. Move the mouse over it, or hold
// a finger on it, and they walk over and gather round; move away or let go
// and they wander back. Drawn on a canvas; idle when nothing moves or it's off screen.

const HINT_KEY = "dg:crowd-hint-seen";
const INK = "#111126";

// One figure, drawn once as line art: a tilted white coin for a head with its
// ridged rim showing, and one soft outline for the body and legs, the arms
// only creases inside it. `pose` is "stand", or "a" / "b" for the
// two steps of the walk (stride, then passing).
function figureSvg(pose) {
  const P = {
    stand: { l: 0, r: 0, lift: 0, arm: 0, lean: 0 },
    a: { l: -4.5, r: 4.5, lift: 1.5, arm: 3, lean: 2 },
    b: { l: 2, r: -2, lift: 0.5, arm: -1, lean: 1 },
  }[pose];
  const f = (n) => n.toFixed(1);
  const [L, R] = [P.l, P.r];
  // Widen the body about its middle (x 60) without touching the strokes.
  const X = (x) => f(60 + (x - 60) * 1.24);
  const body = [
    `M${X(53)} 74`,
    `C${X(47)} 76 ${X(43.5)} 82 ${X(43)} 91`, // left shoulder
    `C${X(42.5)} 101 ${X(42.5)} 112 ${X(44)} 121`, // left side down to the hip
    `C${X(44 + L * 0.5)} 131 ${X(44.5 + L)} 139 ${X(45 + L)} ${f(145 - P.lift)}`, // left leg, outer
    `C${X(45 + L)} ${f(150.5 - P.lift)} ${X(58 + L)} ${f(150.5 - P.lift)} ${X(58.5 + L)} ${f(145.5 - P.lift)}`, // left foot
    `C${X(59 + L * 0.6)} 138 ${X(59.5)} 131 ${X(60)} 127`, // up the inside of the left leg
    `C${X(60.5)} 131 ${X(61 + R * 0.6)} 138 ${X(61.5 + R)} 146`, // down the inside of the right leg
    `C${X(62 + R)} 151 ${X(75 + R)} 151 ${X(75 + R)} 145.5`, // right foot
    `C${X(75.5 + R)} 139 ${X(76 + R * 0.5)} 131 ${X(76)} 121`, // right leg, outer
    `C${X(77.5)} 112 ${X(77.5)} 101 ${X(77)} 91`,
    `C${X(76.5)} 82 ${X(73)} 76 ${X(67)} 74Z`,
  ].join(" ");
  const creases = [
    `M${X(49)} 90C${X(46.5 - P.arm)} 99 ${X(46.5 - P.arm)} 109 ${X(48.5 - P.arm)} 117`, // left arm
    `M${X(71)} 90C${X(73.5 + P.arm)} 99 ${X(73.5 + P.arm)} 109 ${X(71.5 + P.arm)} 117`, // right arm
  ].join("");
  // The coin: a face and, offset behind it, the rim with its ridges.
  const [cx, cy, r, dx, dy] = [64, 43, 28, 13, 2];
  const ridges = [];
  for (let a = 112; a <= 248; a += 12) {
    const t = (a * Math.PI) / 180;
    const x = cx + Math.cos(t) * r;
    const y = cy + Math.sin(t) * r;
    ridges.push(`M${f(x - 1.5)} ${f(y)}L${f(x - dx + 1.5)} ${f(y + dy)}`);
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160">
<ellipse cx="60" cy="150" rx="29" ry="6" fill="${INK}"/>
<g fill="#fff" stroke="${INK}" stroke-linejoin="round" stroke-linecap="round" transform="rotate(${P.lean} 60 150)">
<path d="${body}" stroke-width="4"/>
<path d="${creases}" fill="none" stroke-width="3"/>
<g transform="rotate(8 ${cx} ${cy})">
<circle cx="${cx - dx}" cy="${cy + dy}" r="${r}" stroke-width="4"/>
<path d="${ridges.join("")}" fill="none" stroke-width="3.2"/>
<circle cx="${cx}" cy="${cy}" r="${r}" stroke-width="4"/>
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
    c.width = Math.round(px * (120 / 160));
    c.height = Math.round(px);
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    out[pose] = c;
  }
  return out;
}

// `count` people: `done` of them (picked at random) wear a check mark, and
// seats past `present` are still empty and drawn faded.
function makePeople(width, height, base, floor, count, done, present) {
  const checked = new Set(
    Array.from({ length: count }, (_, i) => i)
      .sort(() => Math.random() - 0.5)
      .slice(0, done),
  );
  // Feet no higher than `floor`, so heads stay clear of the banner's text.
  const top = Math.max(height * 0.5, floor);
  const bottom = height - 6; // everyone fully in view, so they can be counted
  return Array.from({ length: count }, (_, i) => {
    const edge = base * 0.35;
    const x = edge + ((i + 0.5) / count) * (width - 2 * edge) + (Math.random() - 0.5) * base * 0.3;
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
      checked: checked.has(i),
      empty: i < count - present, // the ones who came fill in from the right (RTL)
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
  const w = h * (120 / 160);
  const bob = moving < 0.35 ? 0 : Math.abs(Math.sin(p.phase)) * h * 0.035;
  ctx.save();
  if (p.empty) ctx.globalAlpha = 0.3;
  ctx.translate(p.x, p.y - bob);
  ctx.scale(p.facing, 1);
  // The sprite's feet sit at 150/160 of its height.
  ctx.drawImage(sprites[pose], -w / 2, -h * (150 / 160), w, h);
  ctx.restore();
  if (p.checked) drawCheck(ctx, p.x, p.y - bob - h * (136 / 160), h);
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
// seats are taken while the group is still filling up.
export default function CoinCrowd({ title, text, count = 12, done = 0, present = count }) {
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
      base = Math.max(64, Math.min(210, height * 0.34)); // bigger on a full-screen banner
      // The hint may sit over the crowd's heads; only the title and subtitle can't.
      const hintEl = textBox.current.querySelector(".crowd-hint");
      const textEnd = hintEl ? hintEl.offsetTop : textBox.current.offsetHeight;
      floor = textBox.current.offsetTop + textEnd + 8 + base * 1.2; // room for a check mark too
      people = makePeople(width, height, base, floor, count, Math.min(done, count), present);
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
          if (d > 0 && d < space) {
            push += (ox / d) * (space - d) * 0.05;
            pushY += (oy / d) * (space - d) * 0.03;
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
  }, [count, done, present]);

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
