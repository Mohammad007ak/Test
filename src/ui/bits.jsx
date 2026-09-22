import { useEffect, useRef, useState } from "react";
import { toPersianDigits } from "../lib/jalali.js";

const AVATAR_TONES = 6;

function initials(name = "") {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "؟";
  if (parts.length === 1) return parts[0].slice(0, 2);
  return parts[0][0] + "‌" + parts[parts.length - 1][0];
}

function toneFor(key = "") {
  let hash = 0;
  for (const ch of key) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return (hash % AVATAR_TONES) + 1;
}

export function Avatar({ name, id, size }) {
  const tone = toneFor(id ?? name);
  return (
    <span
      className={`avatar ${size ?? ""}`}
      style={{ background: `var(--av-${tone})`, color: `var(--av-${tone}-ink)` }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}

export function Money({ amount, className = "", unit = "تومان" }) {
  return (
    <span className={`money ${className}`}>
      {Math.round(amount).toLocaleString("fa-IR")}
      <small>{unit}</small>
    </span>
  );
}

// Counts up from the previous value; used for the headline balance.
export function AnimatedNumber({ value, duration = 900 }) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);

  useEffect(() => {
    const start = performance.now();
    const initial = from.current;
    let frame;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(initial + (value - initial) * eased);
      if (t < 1) frame = requestAnimationFrame(tick);
      else from.current = value;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);

  return Math.round(shown).toLocaleString("fa-IR");
}

export function Ring({ value, size = 56, stroke = 6, label, done = false }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <span className={`ring ${done ? "done" : ""}`} style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle className="ring-track" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} />
        <circle
          className="ring-fill"
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - clamped)}
        />
      </svg>
      <span className="ring-label">{label ?? `${toPersianDigits(Math.round(clamped * 100))}٪`}</span>
    </span>
  );
}

export function EmptyState({ icon: Icon, title, text, action }) {
  return (
    <div className="empty">
      {Icon && (
        <span className="e-icon">
          <Icon size={26} strokeWidth={1.75} />
        </span>
      )}
      <h3>{title}</h3>
      {text && <p>{text}</p>}
      {action}
    </div>
  );
}

export function Skeleton({ height = 16, width = "100%", radius }) {
  return <div className="skeleton" style={{ height, width, borderRadius: radius }} />;
}

export function PageSkeleton() {
  return (
    <div className="page" aria-busy="true" aria-label="در حال بارگذاری">
      <Skeleton height={170} radius={24} />
      <div className="kpis">
        <Skeleton height={86} />
        <Skeleton height={86} />
        <Skeleton height={86} />
      </div>
      <Skeleton height={220} radius={20} />
    </div>
  );
}

export function Segmented({ value, onChange, options }) {
  return (
    <div className="segmented" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          className={value === o.value ? "active" : ""}
          onClick={() => onChange(o.value)}
        >
          {o.label}
          {o.count !== undefined && <span className="count">{toPersianDigits(o.count)}</span>}
        </button>
      ))}
    </div>
  );
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}
