import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  BadgeCheck,
  CalendarClock,
  CheckCircle2,
  CreditCard,
  Fingerprint,
  Hourglass,
  ShieldCheck,
  Trophy,
  Wallet,
  XCircle,
} from "lucide-react";
import Pattern from "../../ui/Pattern.jsx";
import { LogoMark } from "../../ui/Logo.jsx";
import WaitingRoom from "./WaitingRoom.jsx";
import { Money, PageSkeleton, Spinner } from "../../ui/bits.jsx";
import { useToast } from "../../ui/feedback.jsx";
import { api } from "../../lib/api.js";
import { verifyDraw } from "../../lib/fairness.js";
import { planById } from "../../lib/plans.js";
import { formatCompact, formatNumber } from "../../lib/format.js";
import { toPersianDigits } from "../../lib/jalali.js";

const METHOD_LABEL = {
  manual: "درگاه پرداخت",
  wallet: "کسر از کیف پول",
  auto: "کسر از کیف پول",
  guarantee: "ضمانت دیجی‌پی",
};

const short = (hex) => (hex ? `${hex.slice(0, 10)}…${hex.slice(-6)}` : "—");

function seatName(member) {
  if (!member) return "—";
  if (member.isOperator) return "دیجی‌پی";
  if (member.isMe) return "شما";
  return `عضو ${toPersianDigits(member.position)}`;
}

function DrawRow({ draw, members, digest }) {
  const [result, setResult] = useState(null);
  const [checking, setChecking] = useState(false);
  const winner = members.find((m) => m.id === draw.winner);

  const check = async () => {
    setChecking(true);
    setResult(await verifyDraw({ ...draw, digest }));
    setChecking(false);
  };

  return (
    <li>
      <span className={`dot ${draw.kind === "operator" ? "pending" : ""}`}>
        {draw.kind === "operator" ? <ShieldCheck size={15} /> : <Trophy size={15} />}
      </span>
      <div className="t-body">
        <div>
          <strong>
            ماه {formatNumber(draw.month)}: {seatName(winner)}
          </strong>
          <span>
            {draw.kind === "operator"
              ? "سهم مدیر و ضامن صندوق"
              : draw.kind === "last"
                ? "آخرین عضو باقی‌مانده"
                : `قرعه بین ${formatNumber(draw.eligible.length)} نفر`}
            ، {formatCompact(draw.pot)} تومان
          </span>
          {result && (
            <span className={result.ok ? "verify ok" : "verify bad"}>
              {result.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
              {result.ok
                ? "درست است: حلقه‌ی زنجیره معتبر است و همین برنده از داده‌ها درمی‌آید."
                : result.linkOk
                  ? "نتیجه با داده‌ها نمی‌خواند!"
                  : "حلقه‌ی زنجیره نامعتبر است!"}
            </span>
          )}
        </div>
        {draw.kind === "lottery" && (
          <button className="btn sm outline" onClick={check} disabled={checking}>
            {checking ? <Spinner /> : <BadgeCheck size={15} />} بررسی
          </button>
        )}
      </div>
    </li>
  );
}

export default function CircleView({ circleId, back, open }) {
  const [view, setView] = useState(null);
  const [error, setError] = useState(null);
  const [paying, setPaying] = useState(false);
  const toast = useToast();

  const load = useCallback(() => api("GET", `/api/circles/${circleId}`).then(setView, setError), [circleId]);
  useEffect(() => {
    load();
  }, [load]);

  // While the group is filling, check every few seconds.
  const status = view?.circle.status;
  const previous = useRef(status);
  useEffect(() => {
    if (previous.current === "forming" && status === "active") toast("گروه شما تکمیل شد و دوره شروع شد 🎉");
    previous.current = status;
    if (status !== "forming") return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [status, load, toast]);

  const header = (
    <header className="appbar">
      <button className="icon-btn" onClick={back} aria-label="بازگشت">
        <ArrowRight size={20} />
      </button>
      <div className="appbar-title">
        <h1>{view ? planById(view.circle.planId)?.title : "دوره"}</h1>
        <div className="sub">
          {view && `سهم ${formatCompact(view.circle.share)}، پات ${formatCompact(view.circle.pot)} تومان`}
        </div>
      </div>
    </header>
  );

  if (error) {
    return (
      <div className="home">
        {header}
        <p className="error-text">{error.message}</p>
      </div>
    );
  }
  if (!view) {
    return (
      <div className="home">
        {header}
        <PageSkeleton />
      </div>
    );
  }

  const { circle, members, draws, contributions } = view;
  const me = members.find((m) => m.isMe);
  const thisMonth = contributions.find((c) => c.month === circle.currentMonth);
  const payable = circle.owed + circle.dueNow;
  const recipientOf = new Map(draws.map((d) => [d.month, members.find((m) => m.id === d.winner)]));

  const pay = async () => {
    setPaying(true);
    try {
      const { checkoutId, redirectUrl } = await api("POST", `/api/circles/${circleId}/pay`);
      if (redirectUrl) window.location.href = redirectUrl;
      else open("checkout", checkoutId);
    } catch (e) {
      toast(e.message, { tone: "error" });
      setPaying(false);
    }
  };

  if (circle.status === "forming" || circle.status === "expired") {
    return (
      <div className="home">
        {header}
        <WaitingRoom view={view} ops={view.ops} reload={load} onLeft={back} onRetry={back} />
      </div>
    );
  }

  let hero;
  if (circle.wonMonth && me) {
    hero = (
      <section className="hero">
        <Pattern />
        <div className="hero-label">
          <Trophy size={16} /> پات را در ماه {formatNumber(circle.wonMonth)} دریافت کردید
        </div>
        <div className="hero-figure">
          {Math.round(circle.pot).toLocaleString("fa-IR")}
          <small>تومان</small>
        </div>
        <p className="hero-sub">
          {circle.status === "completed"
            ? "دوره تمام شد. ممنون از همراهی‌تان."
            : `تا پایان دوره هر ماه ${formatCompact(circle.share)} تومان سهم می‌پردازید.`}
        </p>
      </section>
    );
  } else {
    hero = (
      <section className={`hero ${circle.owed ? "warn" : ""}`}>
        <Pattern />
        <div className="hero-label">
          <CalendarClock size={16} />
          {circle.status === "completed"
            ? "دوره تمام شده"
            : `ماه ${formatNumber(circle.currentMonth)} از ${formatNumber(circle.months)}`}
        </div>
        <div className="hero-figure">
          {Math.round(circle.pot).toLocaleString("fa-IR")}
          <small>تومان پات ماهانه</small>
        </div>
        <p className="hero-sub">
          {circle.owed
            ? `${formatCompact(circle.owed)} تومان بدهی دارید که دیجی‌پی ضمانت کرده؛ تا تسویه در قرعه شرکت داده نمی‌شوید.`
            : `${formatNumber(members.filter((m) => !m.wonMonth).length)} نفر هنوز دریافت نکرده‌اند؛ شانس همه برابر است.`}
        </p>
      </section>
    );
  }

  return (
    <div className="home">
      {header}
      <div className="page">
        {hero}

        {circle.status === "active" && me && (
          <section className="card">
            <div className="split">
              <div className="stack-sm">
                <strong>
                  <CreditCard size={16} /> سهم ماه {formatNumber(circle.currentMonth)}
                </strong>
                <span className="muted small">
                  {thisMonth?.status === "paid" ? (
                    "پرداخت شد. ممنون!"
                  ) : (
                    <>
                      <Wallet size={13} style={{ verticalAlign: "-2px" }} /> اگر تا سررسید پرداخت نکنید، از کیف پولتان
                      کسر می‌شود.
                    </>
                  )}
                </span>
              </div>
              {payable > 0 && (
                <button className="btn primary" onClick={pay} disabled={paying}>
                  {paying ? <Spinner /> : <CreditCard size={17} />} پرداخت {formatCompact(payable)}
                </button>
              )}
            </div>
          </section>
        )}

        {
          <section className="card">
            <div className="section-title">
              <h2>ماه‌های دوره</h2>
              <span className="muted">دریافت‌کننده‌ی هر ماه</span>
            </div>
            <div className="months">
              {Array.from({ length: circle.months }, (_, i) => {
                const month = i + 1;
                const who = recipientOf.get(month);
                const state = who ? "done" : month === circle.currentMonth && circle.status === "active" ? "now" : "";
                return (
                  <div key={month} className={`month-cell ${state} ${who?.isMe ? "mine" : ""}`}>
                    <span>ماه {formatNumber(month)}</span>
                    <b>
                      {who ? seatName(who) : month === 1 ? "دیجی‌پی" : month === circle.currentMonth ? "این ماه" : "—"}
                    </b>
                  </div>
                );
              })}
            </div>
          </section>
        }

        <section className="card">
          <div className="section-title">
            <h2>اعضا</h2>
            <span className="muted">فقط شماره‌ی جایگاه نمایش داده می‌شود</span>
          </div>
          <div className="seats">
            {members.map((m) => (
              <span
                key={m.id}
                className={`seat ${m.isOperator ? "op" : ""} ${m.isMe ? "me" : ""} ${m.wonMonth ? "won" : ""}`}
              >
                {m.isOperator ? <LogoMark size={22} /> : toPersianDigits(m.position)}
                {m.wonMonth && <Trophy size={11} className="seat-badge" />}
              </span>
            ))}
            {Array.from({ length: circle.size - members.length }, (_, i) => (
              <span key={`empty-${i}`} className="seat empty" aria-label="جای خالی" />
            ))}
          </div>
        </section>

        <section className="card">
          <div className="section-title">
            <h2>دفتر قرعه‌کشی</h2>
            <span className="badge brand">
              <Fingerprint size={13} /> قابل اثبات
            </span>
          </div>
          <p className="muted small" style={{ marginBottom: 14 }}>
            پیش از اولین قرعه، اثر انگشت یک زنجیره‌ی رمزنگاری‌شده منتشر شده است. هر قرعه یک حلقه از این زنجیره را آشکار
            می‌کند و برنده از همان حلقه، کد تصادفی گوشی اعضا و شماره‌ی ماه محاسبه می‌شود. با دکمه‌ی «بررسی»، گوشی خودتان
            همین محاسبه را تکرار می‌کند؛ هیچ‌کس، حتی دیجی‌پی، نمی‌تواند نتیجه را عوض کند.
          </p>
          <div className="fingerprints">
            <div>
              <span>اثر انگشت زنجیره</span>
              <code dir="ltr">{short(view.anchor)}</code>
            </div>
            <div>
              <span>کد تصادفی اعضا</span>
              <code dir="ltr">{short(view.nonceDigest)}</code>
            </div>
          </div>
          {draws.length === 0 ? (
            <p className="muted small">هنوز قرعه‌ای انجام نشده.</p>
          ) : (
            <ul className="timeline">
              {[...draws].reverse().map((d) => (
                <DrawRow key={d.month} draw={d} members={members} digest={view.nonceDigest} />
              ))}
            </ul>
          )}
        </section>

        {contributions.length > 0 && (
          <section className="card">
            <div className="section-title">
              <h2>پرداخت‌های شما</h2>
            </div>
            <ul className="ledger">
              {[...contributions].reverse().map((c) => (
                <li key={c.month}>
                  <div>
                    ماه {formatNumber(c.month)}
                    <span>{METHOD_LABEL[c.method] ?? ""}</span>
                  </div>
                  <Money amount={c.amount} />
                  {c.status === "paid" && <span className="badge success">پرداخت شد</span>}
                  {c.status === "settled" && <span className="badge success">تسویه شد</span>}
                  {c.status === "covered" && <span className="badge danger">ضمانت شد، بدهکار</span>}
                  {c.status === "due" && <span className="badge gold">این ماه</span>}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
