import { useEffect, useMemo, useRef, useState } from "react";
import { INK, figureSvg } from "./Figure.jsx";

// A crowd of little people with coin heads. Move the mouse over it, or hold
// a finger on it, and they walk over and gather round; move away or let go
// and they wander back. Drawn on a canvas; idle when nothing moves or it's off screen.

const HINT_KEY = "dg:crowd-hint-seen";

// The kinds of figure in a crowd: an ordinary member (calm or angry), or
// Digi Gharz itself.
const KINDS = { plain: {}, logo: { logo: true }, angry: { angry: true } };

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
// then at random), and seats past `present` are still empty, drawn faded.
function makePeople(width, height, base, floor, count, done, present, cast, angry) {
  const kind = (i) => {
    const k = cast?.[i] ?? "plain";
    return angry && k === "plain" ? "angry" : k;
  };
  const order = Array.from({ length: count }, (_, i) => i).sort(() => Math.random() - 0.5);
  order.sort((a, b) => (kind(b) === "logo") - (kind(a) === "logo"));
  const checked = new Set(order.slice(0, done));
  // Feet no higher than `floor`, so heads stay clear of the banner's text.
  const top = Math.max(height * 0.5, floor);
  const bottom = height - 6; // everyone fully in view, so they can be counted
  const few = count <= 3; // a small group stands together, side by side
  return Array.from({ length: count }, (_, i) => {
    const edge = base * 0.35;
    const x = few
      ? width / 2 + (i - (count - 1) / 2) * base * 0.75
      : edge + ((i + 0.5) / count) * (width - 2 * edge) + (Math.random() - 0.5) * base * 0.3;
    const y = few ? bottom - base * 0.1 : top + Math.random() * (bottom - top);
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
      kind: kind(i),
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
  ctx.save();
  if (p.empty) ctx.globalAlpha = 0.3;
  ctx.translate(p.x + shake, p.y - bob);
  ctx.scale(p.facing, 1);
  // The sprite's feet sit at 150/160 of its height.
  ctx.drawImage(sprites[`${p.kind}:${pose}`], -w / 2, -h * (150 / 160), w, h);
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
// seats are taken while the group is still filling up. `cast` names each
// figure's kind ("plain" or "logo"), by position. `angry` turns the banner
// red and the crowd cross (an installment is unpaid); `action` is a button
// shown under the text.
export default function CoinCrowd({
  title,
  text,
  count = 12,
  done = 0,
  present = count,
  cast,
  angry = false,
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
      people = makePeople(width, height, base, floor, count, Math.min(done, count), present, cast, angry);
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
      // Nearer (lower) people are drawn last so they overlap the ones behind.
      for (const p of [...people].sort((a, b) => a.y - b.y)) drawPerson(ctx, sprites, base, p, t);
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
  }, [count, done, present, castKey, angry]);

  return (
    <div className={`crowd ${angry ? "angry" : ""}`} ref={wrap}>
      <canvas ref={canvas} aria-hidden="true" />
      <div className="crowd-text" ref={textBox}>
        {children}
        <strong>{title}</strong>
        {text && <span>{text}</span>}
        {action}
        {hint && !action && (
          <span className="crowd-hint">{hover ? "موس را روی این‌جا ببرید" : "انگشتتان را جایی نگه دارید 👆"}</span>
        )}
      </div>
    </div>
  );
}
