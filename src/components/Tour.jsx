import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, CalendarCheck, Lock, ShieldCheck, X } from "lucide-react";
import { Figure } from "../ui/Figure.jsx";
import { toPersianDigits } from "../lib/jalali.js";

// A first-visit tour: Digi Gharz itself (the figure with the logo for a
// head) walks a newcomer through the app, one small animated scene per
// idea, "saying" each caption as it types out. Shown once; the home screen
// and the login page can open it again.

const SEEN_KEY = "dg:tour-seen";

export function tourSeen() {
  try {
    return Boolean(localStorage.getItem(SEEN_KEY));
  } catch {
    return true; // no storage: don't nag on every visit
  }
}

function markSeen() {
  try {
    localStorage.setItem(SEEN_KEY, "1");
  } catch {
    // Private mode: it just shows again next time.
  }
}

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

// ---------- the scenes ----------

function Hello() {
  return (
    <div className="scene scene-hello">
      <div className="hop-in">
        <Figure logo size={150} />
      </div>
      <span className="spark s1" />
      <span className="spark s2" />
      <span className="spark s3" />
    </div>
  );
}

function Group() {
  return (
    <div className="scene scene-group">
      <div className="group-grid">
        {Array.from({ length: 12 }, (_, i) => (
          <span key={i} className="pop-in" style={{ animationDelay: `${0.15 + i * 0.12}s` }}>
            <Figure size={52} logo={i === 0} pose={i % 3 === 1 ? "a" : "stand"} />
          </span>
        ))}
      </div>
      <b className="scene-tag fade-in" style={{ animationDelay: "1.8s" }}>
        {n(12)} نفر، هر ماه {n(5)} میلیون
      </b>
    </div>
  );
}

function Pot() {
  return (
    <div className="scene scene-pot">
      <div className="pot-row">
        {Array.from({ length: 6 }, (_, i) => (
          <span key={i} className="pot-giver">
            <Figure size={50} pose={i % 2 ? "a" : "stand"} />
            <i className="coin fly" style={{ "--dx": `${(2.5 - i) * 46}px`, animationDelay: `${0.3 + i * 0.18}s` }} />
          </span>
        ))}
      </div>
      <div className="pot">
        <i className="coin big" />
        <b className="fade-in" style={{ animationDelay: "1.6s" }}>
          {n(60)} میلیون
        </b>
      </div>
    </div>
  );
}

function Draw() {
  const seats = 8;
  return (
    <div className="scene scene-draw">
      <div className="draw-ring">
        {Array.from({ length: seats }, (_, i) => {
          const a = (i / seats) * 2 * Math.PI - Math.PI / 2;
          return (
            <span
              key={i}
              className={`draw-seat ${i === 5 ? "winner" : ""}`}
              style={{
                left: `${50 + Math.cos(a) * 40}%`,
                top: `${50 + Math.sin(a) * 40}%`,
                animationDelay: `${(i * 0.18) % (seats * 0.18)}s`,
              }}
            >
              <Figure size={46} check={false} />
              {i === 5 && (
                <span className="win-check">
                  <Figure size={46} check />
                </span>
              )}
            </span>
          );
        })}
        <span className="draw-lock">
          <Lock size={26} />
        </span>
      </div>
    </div>
  );
}

function Calendar() {
  return (
    <div className="scene scene-calendar">
      <div className="cal-track">
        <span className="cal-fill" />
      </div>
      <ol className="cal-steps">
        <li className="fade-in" style={{ animationDelay: "0.2s" }}>
          <CalendarCheck size={22} />
          <b>سررسید</b>
          <span>روز اول</span>
        </li>
        <li className="fade-in" style={{ animationDelay: "1s" }}>
          <b>{n(5)} روز مهلت</b>
          <span>پرداخت از درگاه</span>
        </li>
        <li className="fade-in" style={{ animationDelay: "1.8s" }}>
          <b>قرعه</b>
          <span>روز ششم</span>
        </li>
      </ol>
    </div>
  );
}

function Guarantee() {
  return (
    <div className="scene scene-guarantee">
      <div className="late">
        <span className="late-calm">
          <Figure size={110} />
        </span>
        <span className="late-angry">
          <Figure size={110} angry />
        </span>
      </div>
      <div className="cover slide-in" style={{ animationDelay: "1.4s" }}>
        <Figure logo size={110} pose="a" />
        <span className="shield">
          <ShieldCheck size={26} />
        </span>
      </div>
    </div>
  );
}

function Family() {
  return (
    <div className="scene scene-family">
      <div className="fam">
        {["stand", "a", "stand", "b"].map((pose, i) => (
          <span key={i} className="pop-in" style={{ animationDelay: `${0.2 + i * 0.2}s` }}>
            <Figure size={i === 1 ? 96 : 80} pose={pose} face={i === 1 ? "#ffc53d" : "#fff"} />
          </span>
        ))}
      </div>
      <b className="scene-tag fade-in" style={{ animationDelay: "1.2s" }}>
        رایگان
      </b>
    </div>
  );
}

function Go() {
  return (
    <div className="scene scene-go">
      {Array.from({ length: 7 }, (_, i) => (
        <span key={i} className="cheer" style={{ animationDelay: `${i * 0.11}s` }}>
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

  const close = () => {
    markSeen();
    onClose();
  };
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
          <span className="tour-guide" aria-hidden="true">
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
