import { useEffect, useMemo, useRef, useState } from "react";
import { BadgeCheck, CheckCircle2, Trophy, X, XCircle } from "lucide-react";
import Confetti from "../../ui/Confetti.jsx";
import Pattern from "../../ui/Pattern.jsx";
import { Spinner } from "../../ui/bits.jsx";
import { verifyDraw } from "../../lib/fairness.js";
import { formatCompact, formatNumber } from "../../lib/format.js";
import { toPersianDigits } from "../../lib/jalali.js";

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// Replays a draw that already happened on the server, the first time a
// member opens the circle after it: the entrants' seats sit in a ring, a
// light runs around it and slows down onto the winner. The result is fixed
// before the animation starts; the "check" button proves it on this phone.
export default function DrawReveal({ draw, members, digest, onClose }) {
  const seats = useMemo(
    () => draw.eligible.map((id) => members.find((m) => m.id === id)).filter(Boolean),
    [draw, members],
  );
  const winnerIndex = Math.max(
    0,
    seats.findIndex((m) => m.id === draw.winner),
  );
  const winner = seats[winnerIndex];
  const me = members.find((m) => m.isMe);
  const iWon = winner?.isMe;

  const [lit, setLit] = useState(-1);
  const [phase, setPhase] = useState("intro"); // intro | spin | done
  const [check, setCheck] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    const finish = () => {
      setLit(winnerIndex);
      setPhase("done");
    };
    if (seats.length < 2 || reducedMotion()) {
      timer.current = setTimeout(finish, 600);
      return () => clearTimeout(timer.current);
    }
    // Two or three laps, then land on the winner, each hop a little slower.
    const steps = (seats.length > 12 ? 2 : 3) * seats.length + winnerIndex;
    let i = 0;
    const hop = () => {
      setLit(i % seats.length);
      if (i === steps) {
        timer.current = setTimeout(finish, 350);
        return;
      }
      const progress = i / steps;
      i += 1;
      timer.current = setTimeout(hop, 45 + 360 * progress ** 3);
    };
    timer.current = setTimeout(() => {
      setPhase("spin");
      hop();
    }, 1100);
    return () => clearTimeout(timer.current);
  }, [seats.length, winnerIndex]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const runCheck = async () => {
    setCheck("busy");
    setCheck(await verifyDraw({ ...draw, digest }));
  };

  // Seats around a ring big enough to hold them all.
  const size = seats.length > 14 ? 36 : 44;
  const radius = Math.max(92, (seats.length * (size + 8)) / (2 * Math.PI));
  const box = radius * 2 + size;
  const label = (m) => (m.isMe ? "شما" : toPersianDigits(m.position));

  return (
    <div className="reveal" role="dialog" aria-modal="true" aria-label={`قرعه‌کشی ماه ${draw.month}`}>
      <Pattern />
      {phase === "done" && iWon && <Confetti count={48} />}
      <button className="reveal-close" onClick={onClose} aria-label="بستن">
        <X size={20} />
      </button>

      <div className="reveal-kicker">
        قرعه‌کشی ماه {formatNumber(draw.month)}، {formatCompact(draw.pot)} تومان
      </div>

      <div className={`reveal-ring ${phase}`} style={{ width: box, height: box }}>
        {seats.map((m, i) => {
          const angle = (i / seats.length) * 2 * Math.PI - Math.PI / 2;
          return (
            <span
              key={m.id}
              className={`rseat ${i === lit ? "lit" : ""} ${m.isMe ? "me" : ""} ${
                phase === "done" && i === winnerIndex ? "win" : ""
              }`}
              style={{
                width: size,
                height: size,
                left: radius + Math.cos(angle) * radius,
                top: radius + Math.sin(angle) * radius,
              }}
            >
              {label(m)}
            </span>
          );
        })}
        <div className="reveal-center" aria-live="polite">
          {phase === "done" ? (
            <>
              <Trophy size={26} />
              <strong>{iWon ? "شما!" : `عضو ${toPersianDigits(winner.position)}`}</strong>
            </>
          ) : (
            <>
              <span>{formatNumber(seats.length)} نفر</span>
              <small>{phase === "intro" ? "آماده…" : "در حال قرعه‌کشی"}</small>
            </>
          )}
        </div>
      </div>

      <div className={`reveal-result ${phase === "done" ? "show" : ""}`}>
        {phase === "done" && (
          <>
            <h2>
              {iWon
                ? `تبریک! ${formatCompact(draw.pot)} تومان مال شماست 🎉`
                : `برنده‌ی این ماه: عضو ${toPersianDigits(winner.position)}`}
            </h2>
            <p>
              {iWon
                ? "مبلغ به کیف پول دیجی‌پی شما واریز می‌شود. تا پایان دوره هر ماه قسطتان را مثل قبل می‌پردازید."
                : me && !me.wonMonth
                  ? "شما در قرعه‌ی ماه بعد هم شرکت دارید؛ کافی است قسطتان را به‌موقع بپردازید."
                  : "همه‌ی اعضا این نتیجه را می‌بینند و می‌توانند درستی‌اش را بررسی کنند."}
            </p>
            {check && check !== "busy" && (
              <span className={`verify ${check.ok ? "ok" : "bad"}`}>
                {check.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                {check.ok ? "گوشی شما هم همین برنده را حساب کرد؛ قرعه دست‌کاری نشده." : "نتیجه با داده‌ها نمی‌خواند!"}
              </span>
            )}
            <div className="reveal-actions">
              {draw.kind === "lottery" && !check && (
                <button className="btn lg reveal-ghost" onClick={runCheck}>
                  <BadgeCheck size={18} /> بررسی درستی قرعه
                </button>
              )}
              {check === "busy" && (
                <button className="btn lg reveal-ghost" disabled>
                  <Spinner />
                </button>
              )}
              <button className="btn gold lg" onClick={onClose}>
                ادامه
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
