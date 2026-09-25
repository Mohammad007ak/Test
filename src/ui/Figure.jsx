// The Digi Gharz character: a little person with a coin for a head, in
// line art. Used as the brand's graphic element across the app, and
// stamped by the home banner's crowd.
import { useMemo } from "react";

export const INK = "#111126";

// One figure: a tilted coin head with its ridged rim showing, and one soft
// outline for the body and legs, the arms only creases inside it. `pose` is
// "stand", or "a" / "b" for the two steps of the walk (stride, then passing).
// `face` colors the coin, `label` writes on it, `check` floats a green check
// over the head, `empty` draws a dashed outline for a seat nobody holds, and
// `logo` makes it Digi Gharz itself, the logo for a face, and `angry` gives
// it a frown and an anger mark (someone's installment is unpaid).
export function figureSvg(
  pose = "stand",
  { face = "#fff", label = "", labelColor = INK, check = false, empty = false, logo = false, angry = false } = {},
) {
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
  // Digi Gharz itself: the logo for a face, Digipay's white chevron and the
  // gold coin under it on a blue coin.
  if (logo) face = "#0000ff";
  const mark = logo
    ? `<path d="M${cx - 12.8} ${cy + 2.4}L${cx} ${cy - 10.4}L${cx + 12.8} ${cy + 2.4}" fill="none" stroke="#fff" stroke-width="7"/><circle cx="${cx}" cy="${cy + 12.8}" r="4.4" fill="#ffc53d" stroke="none"/>`
    : "";
  // Angry: brows down, a frown, and an anger mark over the head (white with
  // an ink outline, so it shows on the red banner too).
  const mood = angry
    ? `<g stroke="${INK}" stroke-width="4" fill="none"><path d="M${cx - 15} ${cy - 11}L${cx - 5} ${cy - 5}M${cx + 15} ${cy - 11}L${cx + 5} ${cy - 5}"/><path d="M${cx - 9} ${cy + 15}Q${cx} ${cy + 7} ${cx + 9} ${cy + 15}"/></g><circle cx="${cx - 8}" cy="${cy + 2}" r="3.2" fill="${INK}" stroke="none"/><circle cx="${cx + 8}" cy="${cy + 2}" r="3.2" fill="${INK}" stroke="none"/>`
    : "";
  const vein = angry
    ? `<g stroke-linecap="round" fill="none" transform="translate(${cx + 22} ${cy - 32}) scale(1.3)">${[INK, "#fff"].map((c, i) => `<path d="M-7 -2q4 0 5-5M2 -7q1 5 5 5M7 2q-4 0-5 5M-2 7q-1-5-5-5" stroke="${c}" stroke-width="${i ? 2.6 : 6}"/>`).join("")}</g>`
    : "";
  // An empty seat is just a dashed outline of someone.
  const paint = empty ? `fill="none" stroke-dasharray="8 6" opacity="0.4"` : `fill="#fff"`;
  const text = label
    ? `<text x="${cx}" y="${cy + 6}" text-anchor="middle" font-size="${label.length > 2 ? 15 : 19}" font-weight="800" fill="${labelColor}" stroke="none" font-family="Estedad Variable, Vazirmatn Variable, Tahoma, sans-serif">${label}</text>`
    : "";
  // A green check floating over the head: this one has been paid.
  const badge = check
    ? `<g stroke="${INK}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="${cx}" cy="-9" r="14" fill="#3ddc84"/><path d="M${cx - 6} -9l4 4 8-9" fill="none"/></g>`
    : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 ${check ? -28 : 0} 120 ${check ? 188 : 160}">
${empty ? "" : `<ellipse cx="60" cy="150" rx="29" ry="6" fill="${INK}"/>`}
<g ${paint} stroke="${INK}" stroke-linejoin="round" stroke-linecap="round" transform="rotate(${P.lean} 60 150)">
<path d="${body}" stroke-width="4"/>
${empty ? "" : `<path d="${creases}" fill="none" stroke-width="3"/>`}
<g transform="rotate(8 ${cx} ${cy})">
${empty ? "" : `<circle cx="${cx - dx}" cy="${cy + dy}" r="${r}" stroke-width="4" fill="${face}"/>`}
${empty ? "" : `<path d="${ridges.join("")}" fill="none" stroke-width="3.2"/>`}
<circle cx="${cx}" cy="${cy}" r="${r}" stroke-width="4" ${empty ? "" : `fill="${face}"`}/>
${text}${mark}${mood}
</g>${vein}
</g>${badge}</svg>`;
}

export function Figure({ pose, size = 48, className = "", title, ...opts }) {
  const key = JSON.stringify([pose, opts]);
  // Keyed on the options' contents, not the object's identity.
  const svg = useMemo(() => figureSvg(pose, opts), [key]);
  return (
    <span
      className={`figure ${className}`}
      style={{ "--fig-h": `${opts.check ? (size * 188) / 160 : size}px` }} // the badge adds height, not shrinks the figure
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      title={title}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
