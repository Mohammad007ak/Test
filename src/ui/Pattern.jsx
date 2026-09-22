import { useId } from "react";

// An eight-pointed star lattice (khatam), the brand's quiet Persian signature.
export default function Pattern({ size = 56 }) {
  const id = useId();
  const s = size;
  const c = s / 2;
  const r = s * 0.36;
  const q = s * 0.25;
  const star = [0, 1, 2, 3, 4, 5, 6, 7]
    .map((i) => {
      const a = (Math.PI / 4) * i;
      const radius = i % 2 ? r * 0.72 : r;
      return `${c + radius * Math.cos(a)},${c + radius * Math.sin(a)}`;
    })
    .join(" ");

  return (
    <svg className="pattern" aria-hidden="true" width="100%" height="100%">
      <defs>
        <pattern id={id} width={s} height={s} patternUnits="userSpaceOnUse">
          <g fill="none" stroke="currentColor" strokeWidth="1">
            <polygon points={star} />
            <rect x={c - q} y={c - q} width={q * 2} height={q * 2} transform={`rotate(45 ${c} ${c})`} />
            <path d={`M${c} 0V${c - r} M${c} ${s}V${c + r} M0 ${c}H${c - r} M${s} ${c}H${c + r}`} />
          </g>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
    </svg>
  );
}
