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

// A tomato in flight: red, an ink outline, a green top, spinning.
function drawTomato(ctx, x, y, r, spin) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(spin);
  ctx.lineWidth = Math.max(1.5, r * 0.22);
  ctx.strokeStyle = INK;
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
  ctx.lineWidth = Math.max(1, r * 0.14);
  ctx.stroke();
  ctx.restore();
}

// A tomato after it lands: a red splat with drips and seeds, fading away.
function drawSplat(ctx, x, y, r, s, alpha) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.translate(x, y);
  ctx.rotate(s.rot);
  ctx.lineWidth = Math.max(1.5, r * 0.14);
  ctx.strokeStyle = INK;
  ctx.fillStyle = "#ff5b45";
  ctx.beginPath();
  s.lobes.forEach((k, i) => {
    const a = (i / s.lobes.length) * Math.PI * 2;
    const rr = r * k;
    ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr);
  });
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  for (const d of s.drips) {
    ctx.beginPath();
    ctx.ellipse(d.x * r, r * 0.6 + d.len * r * s.age, r * 0.16, r * (0.2 + d.len * s.age * 0.6), 0, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = "#ffc53d";
  for (const d of s.seeds) {
    ctx.beginPath();
    ctx.ellipse(d.x * r, d.y * r, r * 0.1, r * 0.06, d.a, 0, Math.PI * 2);
    ctx.fill();
  }
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
  meDone = false,
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
    // When the member's installment is unpaid, every few seconds one of the
    // cross members lobs a tomato at them.
    let tomatoes = [];
    let splats = [];
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
      tomatoes = [];
      splats = [];
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
      const r = base * 0.1;
      for (const s of splats) {
        const h = base * s.who.size;
        s.age = Math.min(1, (t - s.t) / 1800);
        const alpha = s.age < 0.6 ? 1 : 1 - (s.age - 0.6) / 0.4;
        drawSplat(ctx, s.who.x + s.ox * h, s.who.y - h * 0.72 + s.oy * h, r * 1.7, s, alpha);
      }
      for (const m of tomatoes) drawTomato(ctx, m.x, m.y, r, m.spin);
    };

    const throwTomatoes = (t) => {
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
        tomatoes.push({ x0: from.x + from.facing * h * 0.25, y0: from.y - h * 0.62, t0: t, dur: 520 + dist * 0.9 });
        nextThrow = t + 2400 + Math.random() * 1800;
      }
      const h = base * me.size;
      // Head for where the member's head is now, even if they've moved.
      const tx = me.x;
      const ty = me.y - h * 0.8;
      tomatoes = tomatoes.filter((m) => {
        const k = (t - m.t0) / m.dur;
        if (k >= 1) {
          me.hitT = t;
          splats.push({
            who: me,
            t,
            ox: (Math.random() - 0.5) * 0.2,
            oy: (Math.random() - 0.5) * 0.12,
            rot: Math.random() * Math.PI,
            lobes: Array.from({ length: 12 }, (_, i) => (i % 2 ? 0.6 : 0.9) + Math.random() * 0.35),
            drips: Array.from({ length: 3 }, () => ({
              x: (Math.random() - 0.5) * 1.1,
              len: 0.4 + Math.random() * 0.8,
            })),
            seeds: Array.from({ length: 4 }, () => ({
              x: (Math.random() - 0.5) * 0.9,
              y: (Math.random() - 0.5) * 0.9,
              a: Math.random() * Math.PI,
            })),
            age: 0,
          });
          return false;
        }
        m.x = m.x0 + (tx - m.x0) * k;
        m.y = m.y0 + (ty - m.y0) * k - base * 0.9 * 4 * k * (1 - k);
        m.spin = k * Math.PI * 3;
        return true;
      });
      splats = splats.filter((s) => t - s.t < 1800);
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
      if (angry) throwTomatoes(t);
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
  }, [count, done, present, castKey, angry, meDone]);

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
