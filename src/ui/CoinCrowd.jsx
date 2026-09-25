import { useEffect, useRef, useState } from "react";

// A crowd of little people with coin heads. Press and hold anywhere on it
// (mouse or finger) and they walk over and gather round; let go and they
// wander back. Drawn on a canvas; idle when nothing moves or it's off screen.

const BODY = ["#ffffff", "#c9ccff", "#9aa0ff", "#e8e8ff"];
const HINT_KEY = "dg:crowd-hint-seen";
const SPACE = 14; // px two people keep between them

function makePeople(width, height) {
  const count = Math.max(14, Math.min(56, Math.round(width / 13)));
  return Array.from({ length: count }, (_, i) => {
    // Spread along the lower part of the banner, a little jittered.
    const x = 14 + ((i + 0.5) / count) * (width - 28) + (Math.random() - 0.5) * 14;
    const y = height * (0.52 + Math.random() * 0.4);
    return {
      homeX: x,
      homeY: y,
      x,
      y,
      vx: 0,
      vy: 0,
      size: 0.8 + ((y - height * 0.52) / (height * 0.4)) * 0.35,
      color: BODY[i % BODY.length],
      speed: 0.7 + Math.random() * 0.6,
      phase: Math.random() * Math.PI * 2,
      spin: Math.random() * Math.PI * 2,
      slot: 0,
    };
  });
}

function drawPerson(ctx, p, t) {
  const s = p.size;
  const moving = Math.hypot(p.vx, p.vy);
  const step = Math.min(1, moving / 1.5);
  const bob = Math.sin(p.phase) * 2.2 * step;
  const x = p.x;
  const y = p.y - bob;

  // Legs swing while walking.
  const swing = Math.sin(p.phase) * 4 * s * step;
  ctx.strokeStyle = p.color;
  ctx.lineWidth = 3 * s;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(x - 2.5 * s, y - 6 * s);
  ctx.lineTo(x - 2.5 * s + swing, y);
  ctx.moveTo(x + 2.5 * s, y - 6 * s);
  ctx.lineTo(x + 2.5 * s - swing, y);
  ctx.stroke();

  // Body: a rounded capsule.
  const bw = 11 * s;
  const bh = 15 * s;
  ctx.fillStyle = p.color;
  ctx.beginPath();
  ctx.roundRect(x - bw / 2, y - 6 * s - bh, bw, bh, 5 * s);
  ctx.fill();

  // Head: a gold coin that flips while it hurries.
  const r = 7.5 * s;
  const hy = y - 6 * s - bh - r + 1.5 * s;
  const flip = 0.35 + 0.65 * Math.abs(Math.cos(p.spin + t * 0.002 * step));
  ctx.save();
  ctx.translate(x, hy);
  ctx.scale(flip, 1);
  ctx.fillStyle = "#e09a00";
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#ffc53d";
  ctx.beginPath();
  ctx.arc(0, 0, r * 0.78, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(255,255,255,0.55)";
  ctx.beginPath();
  ctx.arc(-r * 0.3, -r * 0.3, r * 0.22, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export default function CoinCrowd({ title, text }) {
  const wrap = useRef(null);
  const canvas = useRef(null);
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
    let frame = 0;
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
      people = makePeople(width, height);
      draw(performance.now());
      wake();
    };

    const draw = (t) => {
      ctx.clearRect(0, 0, width, height);
      // Nearer (lower) people are drawn last so they overlap the ones behind.
      for (const p of [...people].sort((a, b) => a.y - b.y)) drawPerson(ctx, p, t);
    };

    const tick = (t) => {
      frame = 0;
      let busy = pointer.down;
      for (const p of people) {
        let tx = p.homeX;
        let ty = p.homeY;
        if (pointer.down) {
          const ring = 14 + 9.5 * Math.sqrt(p.slot);
          const angle = p.slot * 2.39996; // golden angle: an even, tight cluster
          tx = pointer.x + Math.cos(angle) * ring;
          ty = pointer.y + 14 + Math.sin(angle) * ring * 0.7;
        }
        const dx = tx - p.x;
        const dy = ty - p.y;
        const pull = (pointer.down ? 0.012 : 0.006) * p.speed;
        // Keep a little personal space so the crowd doesn't pile up.
        let push = 0;
        let pushY = 0;
        for (const q of people) {
          if (q === p) continue;
          const ox = p.x - q.x;
          const oy = (p.y - q.y) * 1.6;
          const d = Math.hypot(ox, oy);
          if (d > 0 && d < SPACE) {
            push += (ox / d) * (SPACE - d) * 0.05;
            pushY += (oy / d) * (SPACE - d) * 0.03;
          }
        }
        p.vx = (p.vx + dx * pull + push) * 0.86;
        p.vy = (p.vy + dy * pull + pushY) * 0.86;
        const cap = 4.5 * p.speed;
        const v = Math.hypot(p.vx, p.vy);
        if (v > cap) {
          p.vx *= cap / v;
          p.vy *= cap / v;
        }
        p.x += p.vx;
        p.y += p.vy;
        p.phase += 0.1 + v * 0.12;
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
      <div className="crowd-text">
        <strong>{title}</strong>
        {text && <span>{text}</span>}
      </div>
      {hint && <span className="crowd-hint">انگشتتان را جایی نگه دارید 👆</span>}
    </div>
  );
}
