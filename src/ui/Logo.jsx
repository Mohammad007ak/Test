// A chest (صندوقچه) whose lid carries an eight-pointed star.
export function LogoMark({ size = 34, light = false }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect width="40" height="40" rx="12" fill={light ? "rgb(255 255 255 / 0.12)" : "var(--brand)"} />
      <path d="M9 17h22v13a3 3 0 0 1-3 3H12a3 3 0 0 1-3-3z" fill={light ? "#fff" : "var(--brand-ink)"} opacity="0.95" />
      <path d="M9 17c0-5 4.5-9 11-9s11 4 11 9z" fill={light ? "#fff" : "var(--brand-ink)"} opacity="0.6" />
      <path
        d="M20 19.5l1.2 2.1 2.3-.6-.6 2.3 2.1 1.2-2.1 1.2.6 2.3-2.3-.6-1.2 2.1-1.2-2.1-2.3.6.6-2.3-2.1-1.2 2.1-1.2-.6-2.3 2.3.6z"
        fill="#e6a92c"
      />
    </svg>
  );
}

export function Logo({ light = false }) {
  return (
    <div className="brand">
      <LogoMark light={light} />
      صندوقچه
    </div>
  );
}
