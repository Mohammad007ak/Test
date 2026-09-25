import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, CalendarCheck, Lock, ShieldCheck, X } from "lucide-react";
import { Figure } from "../ui/Figure.jsx";
import Confetti from "../ui/Confetti.jsx";
import { toPersianDigits } from "../lib/jalali.js";

// A first-visit tour: Digi Gharz itself (the figure with the logo for a
// head) walks a newcomer through the app, one small animated scene per
// idea, "saying" each caption as it types out. Every new account sees it
// once right after signing in; the home screen and login page reopen it.

const still = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// Types a caption out a letter at a time, like someone speaking it.
function useTyped(text) {
  const [shown, setShown] = useState(() => (still() ? text.length : 0));
  useEffect(() => {
    if (still()) return setShown(text.length);
    setShown(0);
    const t = setInterval(() => setShown((n) => (n >= text.length ? n : n + 1)), 28);
    return () => clearInterval(t);
  }, [text]);
  return { text: text.slice(0, shown), done: shown >= text.length };
}

const n = toPersianDigits;

// ---------- helpers ----------

// A number that counts up to `to` over `ms`, after `delay`.
function useCount(to, ms = 1200, delay = 0) {
  const [v, setV] = useState(() => (still() ? to : 0));
  useEffect(() => {
    if (still()) return setV(to);
    let raf = 0;
    const start = performance.now() + delay;
    const tick = (t) => {
      const k = Math.min(1, Math.max(0, (t - start) / ms));
      setV(Math.round(to * (1 - (1 - k) ** 3)));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, ms, delay]);
  return v;
}

// True once `ms` have passed since the scene appeared.
function useAfter(ms) {
  const [on, setOn] = useState(() => still());
  useEffect(() => {
    const t = setTimeout(() => setOn(true), still() ? 0 : ms);
    return () => clearTimeout(t);
  }, [ms]);
  return on;
}

// A confetti burst that leaves no layers behind once it has fallen.
function Burst({ count }) {
  const over = useAfter(1800);
  return over ? null : <Confetti count={count} />;
}

// A walking figure: its two steps alternate while it moves.
function Walker({ size, ...opts }) {
  return (
    <span className="walker">
      <Figure size={size} pose="a" {...opts} />
      <Figure size={size} pose="b" {...opts} />
    </span>
  );
}

const rain = Array.from({ length: 12 }, (_, i) => ({
  left: `${(i * 37) % 100}%`,
  delay: `${(i * 0.23) % 2.2}s`,
  size: 14 + ((i * 7) % 12),
}));

// ---------- the scenes ----------

// Digi Gharz drops out of the sky, squashes on landing, springs up and
// waves hello, while coins rain behind it.
function Hello() {
  return (
    <div className="scene scene-hello">
      {rain.map((r, i) => (
        <i
          key={i}
          className="coin rain"
          style={{ left: r.left, animationDelay: r.delay, width: r.size, height: r.size }}
        />
      ))}
      <div className="drop-in">
        <div className="squash-land">
          <div className="wave-hi">
            <Figure logo size={150} />
          </div>
        </div>
      </div>
      <span className="say-pop">سلام!</span>
    </div>
  );
}

// Twelve drop in one by one while the count ticks up, then do a stadium wave.
function Group() {
  const count = useCount(12, 1400, 200);
  return (
    <div className="scene scene-group">
      <div className="group-grid">
        {Array.from({ length: 12 }, (_, i) => (
          <span key={i} className="drop-in small" style={{ animationDelay: `${0.15 + i * 0.11}s` }}>
            <span className="stadium" style={{ animationDelay: `${2 + (i % 6) * 0.09 + Math.floor(i / 6) * 0.3}s` }}>
              <Figure size={50} logo={i === 0} />
            </span>
          </span>
        ))}
      </div>
      <b className="scene-tag counter">{n(count)} نفر</b>
    </div>
  );
}

// Everyone flips a coin into the pot: coins arc over and spin as they fly,
// the pot jiggles with each one and the total rolls up to 60 million.
function Pot() {
  const total = useCount(60, 1500, 700);
  const full = useAfter(2300);
  return (
    <div className="scene scene-pot">
      <div className="pot-row">
        {Array.from({ length: 6 }, (_, i) => (
          <span key={i} className="pot-giver">
            <span className="toss" style={{ animationDelay: `${0.3 + i * 0.2}s` }}>
              <Figure size={50} pose={i % 2 ? "a" : "stand"} />
            </span>
            <span className="coin-x" style={{ "--dx": `${(2.5 - i) * 46}px`, animationDelay: `${0.35 + i * 0.2}s` }}>
              <span className="coin-y" style={{ animationDelay: `${0.35 + i * 0.2}s` }}>
                <i className="coin spin" />
              </span>
            </span>
          </span>
        ))}
      </div>
      <div className={`pot ${full ? "full" : ""}`}>
        <i className="coin big spin" />
        <b>{n(total)} میلیون</b>
      </div>
      {full && <Burst count={24} />}
    </div>
  );
}

// A drumroll: the light hops round the ring, slowing down, while everyone
// trembles; it stops on the winner, who jumps for joy under confetti.
function Draw() {
  const seats = 8;
  const winner = 5;
  const [lit, setLit] = useState(-1);
  const [done, setDone] = useState(() => still());
  useEffect(() => {
    if (still()) return setLit(winner);
    const steps = 2 * seats + winner;
    let i = 0;
    let t;
    const hop = () => {
      setLit(i % seats);
      if (i === steps) return (t = setTimeout(() => setDone(true), 250));
      const k = i / steps;
      i += 1;
      t = setTimeout(hop, 55 + 330 * k ** 3);
    };
    t = setTimeout(hop, 500);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="scene scene-draw">
      <div className={`draw-ring ${done ? "done" : "spinning"}`}>
        {Array.from({ length: seats }, (_, i) => {
          const a = (i / seats) * 2 * Math.PI - Math.PI / 2;
          const won = done && i === winner;
          return (
            <span
              key={i}
              className={`draw-seat ${i === lit ? "lit" : ""} ${won ? "won" : ""}`}
              style={{ left: `${50 + Math.cos(a) * 40}%`, top: `${50 + Math.sin(a) * 40}%`, "--i": i }}
            >
              <Figure size={46} check={won} face={i === lit ? "#ffc53d" : "#fff"} />
            </span>
          );
        })}
        <span className="draw-lock">{done ? "🎉" : <Lock size={24} />}</span>
      </div>
      {done && <Burst count={30} />}
      {!done && <b className="drumroll">دررررر…</b>}
    </div>
  );
}

// A little figure walks the month: due date, five days to pay, draw day,
// stopping at each; the stops light up as it arrives.
function Calendar() {
  const party = useAfter(3300);
  return (
    <div className="scene scene-calendar">
      <div className="cal-road">
        <span className="cal-walker">
          <Walker size={58} />
        </span>
        <span className="cal-track">
          <span className="cal-fill" />
        </span>
      </div>
      <ol className="cal-steps">
        <li className="stop s1">
          <CalendarCheck size={20} />
          <b>سررسید</b>
          <span>روز اول</span>
        </li>
        <li className="stop s2">
          <b>{n(5)} روز مهلت</b>
          <span>پرداخت از درگاه</span>
        </li>
        <li className="stop s3">
          <b>قرعه</b>
          <span>روز ششم</span>
        </li>
      </ol>
      {party && <Burst count={20} />}
    </div>
  );
}

// Someone skips a payment: the stage flashes red, they shake with steam
// coming off their head; Digi Gharz swoops in with a shield to cover.
function Guarantee() {
  return (
    <div className="scene scene-guarantee">
      <div className="late">
        <span className="late-calm">
          <Figure size={110} />
        </span>
        <span className="late-angry">
          <span className="fume">
            <Figure size={110} angry />
          </span>
          <i className="steam s1" />
          <i className="steam s2" />
          <i className="steam s3" />
        </span>
      </div>
      <div className="swoop">
        <div className="squash-land late-land">
          <Figure logo size={110} pose="a" />
        </div>
        <span className="shield">
          <ShieldCheck size={26} />
        </span>
      </div>
    </div>
  );
}

// The family hops into place and a roof draws itself over them: free.
function Family() {
  return (
    <div className="scene scene-family">
      <svg className="roof" viewBox="0 0 300 90" aria-hidden="true">
        <path d="M20 86 L150 12 L280 86" />
      </svg>
      <div className="fam">
        {["stand", "a", "stand", "b"].map((pose, i) => (
          <span key={i} className="hop-line" style={{ animationDelay: `${0.2 + i * 0.22}s` }}>
            <Figure size={i === 1 ? 96 : 80} pose={pose} face={i === 1 ? "#ffc53d" : "#fff"} />
          </span>
        ))}
      </div>
      <b className="scene-tag wobble">رایگان!</b>
    </div>
  );
}

// Everyone jumps for joy; Digi Gharz does a flip; confetti.
function Go() {
  return (
    <div className="scene scene-go">
      <Burst count={40} />
      {Array.from({ length: 7 }, (_, i) => (
        <span key={i} className={i === 3 ? "flip-jump" : "cheer"} style={{ animationDelay: `${i * 0.11}s` }}>
          <Figure size={i === 3 ? 120 : 76} logo={i === 3} pose={i % 2 ? "a" : "b"} />
        </span>
      ))}
    </div>
  );
}

const STEPS = [
  {
    Scene: Hello,
    title: "سلام! من دیجی قرضم",
    say: "این‌جا با هم وام می‌گیریم؛ بدون ضامن، بدون بهره. بیا در یک دقیقه نشانت بدهم چطور کار می‌کند.",
  },
  {
    Scene: Group,
    title: "یک گروه، چند نفر",
    say: "در هر طرح، مثلاً ۱۲ نفر یک گروه می‌شوند و هر ماه هر کدام یک قسط ثابت می‌گذارند. جایگاه اول مال من است.",
  },
  {
    Scene: Pot,
    title: "هر ماه یک‌جا به یک نفر",
    say: "قسط همه جمع می‌شود و کل مبلغ، مثلاً ۶۰ میلیون تومان، یک‌جا به یک نفر می‌رسد. تا آخر دوره نوبت همه می‌شود.",
  },
  {
    Scene: Draw,
    title: "قرعه‌ی قابل اثبات",
    say: "برنده‌ی هر ماه با قرعه معلوم می‌شود. نتیجه از قبل قفل است و خودت با یک دکمه درستی‌اش را بررسی می‌کنی؛ حتی من هم نمی‌توانم تقلب کنم!",
  },
  {
    Scene: Calendar,
    title: "تقویم هر ماه",
    say: "هر ماه روز سررسید، قسطت را از درگاه می‌دهی و ۵ روز مهلت داری. روز ششم قرعه‌کشی است و مبلغ همان روز واریز می‌شود.",
  },
  {
    Scene: Guarantee,
    title: "ضمانت دیجی‌پی",
    say: "اگر قسطی جا بماند، من جایش می‌پردازم تا مبلغ برنده کامل باشد؛ ولی تا تسویه در قرعه نیستی و جریمه‌ی تأخیر دارد. قسطت را به‌موقع بده تا بقیه عصبانی نشوند!",
  },
  {
    Scene: Family,
    title: "صندوق خانوادگی",
    say: "صندوق فامیلی خودتان را هم می‌توانی رایگان این‌جا بسازی: سهم‌ها، قرعه و وام‌ها بدون دفترچه، برای همه‌ی اعضا شفاف.",
  },
  {
    Scene: Go,
    title: "آماده‌ای؟",
    say: "همین! از بالای صفحه طرحت را انتخاب کن. هر وقت خواستی، این راهنما از دکمه‌ی «راهنما» دوباره باز می‌شود.",
  },
];

export default function Tour({ onClose }) {
  const [step, setStep] = useState(0);
  const { Scene, title, say } = STEPS[step];
  const caption = useTyped(say);
  const last = step === STEPS.length - 1;
  const swipe = useRef(null);

  const close = () => onClose();
  const next = () => (last ? close() : setStep((s) => s + 1));
  const prev = () => setStep((s) => Math.max(0, s - 1));

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") close();
      // Right-to-left: the left arrow moves forward.
      if (e.key === "ArrowLeft") next();
      if (e.key === "ArrowRight") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="tour" role="dialog" aria-modal="true" aria-label="آشنایی با دیجی قرض">
      <div className="tour-card">
        <button className="tour-skip" onClick={close}>
          رد شدن <X size={16} />
        </button>

        <div
          className="tour-stage"
          onPointerDown={(e) => (swipe.current = e.clientX)}
          onPointerUp={(e) => {
            if (swipe.current === null) return;
            const dx = e.clientX - swipe.current;
            swipe.current = null;
            if (dx < -50) next();
            if (dx > 50) prev();
          }}
        >
          <Scene key={step} />
        </div>

        <div className="tour-talk">
          <span className={`tour-guide ${caption.done ? "" : "talking"}`} aria-hidden="true">
            <Figure logo size={64} pose={caption.done ? "stand" : "a"} />
          </span>
          <div className="tour-bubble" aria-live="polite">
            <strong>{title}</strong>
            <p>
              {caption.text}
              {!caption.done && <span className="caret" />}
            </p>
          </div>
        </div>

        <div className="tour-nav">
          <button className="btn outline" onClick={prev} disabled={step === 0} aria-label="قبلی">
            <ArrowRight size={18} />
          </button>
          <div className="tour-dots" aria-label={`مرحله‌ی ${step + 1} از ${STEPS.length}`}>
            {STEPS.map((_, i) => (
              <button
                key={i}
                className={i === step ? "on" : ""}
                onClick={() => setStep(i)}
                aria-label={`مرحله‌ی ${i + 1}`}
              />
            ))}
          </div>
          <button className="btn primary" onClick={next}>
            {last ? "شروع کنیم" : "بعدی"} {!last && <ArrowLeft size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
}
