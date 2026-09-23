// Digipay's chevron on its blue tile, with a coin under it for the loan.
export function LogoMark({ size = 34, light = false }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect width="40" height="40" rx="12" fill={light ? "rgb(255 255 255 / 0.14)" : "var(--brand)"} />
      <path
        d="M12 22.5l8-8 8 8"
        fill="none"
        stroke={light ? "#fff" : "var(--brand-ink)"}
        strokeWidth="4.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="20" cy="29" r="2.6" fill="#ffc53d" />
    </svg>
  );
}

export function Logo({ light = false }) {
  return (
    <div className="brand">
      <LogoMark light={light} />
      دیجی قرض
    </div>
  );
}
