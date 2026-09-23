import { useMemo } from "react";

const COLORS = ["#ffc53d", "#ffd66e", "#5c6bff", "#ffffff", "#0000ff"];

// A one-shot burst from the middle of its (positioned) parent.
export default function Confetti({ count = 36 }) {
  const pieces = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => {
        const angle = (Math.PI * 2 * i) / count + Math.random() * 0.3;
        const dist = 120 + Math.random() * 140;
        return {
          x: `${Math.cos(angle) * dist}px`,
          y: `${Math.sin(angle) * dist - 40}px`,
          r: `${Math.random() * 720 - 360}deg`,
          color: COLORS[i % COLORS.length],
          delay: `${Math.random() * 0.15}s`,
        };
      }),
    [count],
  );
  return (
    <div className="confetti" aria-hidden="true">
      {pieces.map((p, i) => (
        <i key={i} style={{ "--x": p.x, "--y": p.y, "--r": p.r, background: p.color, animationDelay: p.delay }} />
      ))}
    </div>
  );
}
