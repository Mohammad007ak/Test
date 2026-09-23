import { useCallback, useEffect, useRef, useState } from "react";
import {
  BadgeCheck,
  CalendarClock,
  CheckCircle2,
  CreditCard,
  Lock,
  PlayCircle,
  ShieldCheck,
  Smartphone,
  Trophy,
  Wallet,
  XCircle,
} from "lucide-react";
import AppBar from "../../ui/AppBar.jsx";
import Pattern from "../../ui/Pattern.jsx";
import { LogoMark } from "../../ui/Logo.jsx";
import WaitingRoom from "./WaitingRoom.jsx";
import DrawReveal from "./DrawReveal.jsx";
import { PageSkeleton, Spinner } from "../../ui/bits.jsx";
import { useToast } from "../../ui/feedback.jsx";
import { api } from "../../lib/api.js";
import { verifyDraw } from "../../lib/fairness.js";
import { planById } from "../../lib/plans.js";
import { scheduleOf } from "../../lib/schedule.js";
import { formatCompact, formatNumber } from "../../lib/format.js";
import { formatDay, toPersianDigits } from "../../lib/jalali.js";

const DAY = 24 * 60 * 60 * 1000;
const daysUntil = (t) => Math.max(0, Math.ceil((t - Date.now()) / DAY));

const METHOD_LABEL = {
  entry: "هنگام عضویت",
  manual: "از درگاه",
  wallet: "از کیف پول",
  auto: "از کیف پول",
  guarantee: "با ضمانت دیجی‌پی",
};

const short = (hex) => (hex ? `${hex.slice(0, 10)}…${hex.slice(-6)}` : "—");

function seatName(member) {
  if (!member) return "—";
  if (member.isOperator) return "دیجی‌پی";
  if (member.isMe) return "شما";
  return `عضو ${toPersianDigits(member.position)}`;
}

function PaymentBadge({ contribution }) {
  if (!contribution) return <span className="badge">در انتظار</span>;
  if (contribution.status === "paid") return <span className="badge success">پرداخت شد</span>;
  if (contribution.status === "settled") return <span className="badge success">تسویه شد</span>;
  if (contribution.status === "covered") return <span className="badge danger">بدهکار</span>;
  return <span className="badge gold">پرداخت نشده</span>;
}

function DrawRow({ draw, members, digest, onReplay }) {
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
              ? "سهم مدیر و ضامن گروه"
              : draw.kind === "last"
                ? "آخرین نفر باقی‌مانده"
                : `قرعه بین ${formatNumber(draw.eligible.length)} نفر`}
            ، {formatCompact(draw.pot)} تومان
          </span>
          {result && (
            <span className={result.ok ? "verify ok" : "verify bad"}>
              {result.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
              {result.ok ? "درست است؛ گوشی شما هم همین برنده را حساب کرد." : "نتیجه با داده‌ها نمی‌خواند!"}
            </span>
          )}
        </div>
        {draw.kind !== "operator" && (
          <div className="row-end">
            <button className="icon-btn sm soft" onClick={() => onReplay(draw)} aria-label="نمایش دوباره‌ی قرعه">
              <PlayCircle size={16} />
            </button>
            {draw.kind === "lottery" && (
              <button className="btn sm outline" onClick={check} disabled={checking}>
                {checking ? <Spinner /> : <BadgeCheck size={15} />} بررسی
              </button>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

export default function CircleView({ circleId, back, open }) {
  const [view, setView] = useState(null);
  const [error, setError] = useState(null);
  const [paying, setPaying] = useState(false);
  const [reveal, setReveal] = useState(null);
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

  // A draw this member hasn't watched yet plays once, the first time they
  // open the circle after it.
  const latestDraw = view?.draws.at(-1);
  useEffect(() => {
    if (!view || !latestDraw || !view.members.some((m) => m.isMe)) return;
    if (latestDraw.month <= view.circle.seenMonth) return;
    if (latestDraw.kind !== "operator") setReveal(latestDraw);
    api("POST", `/api/circles/${circleId}/seen`, { month: latestDraw.month }).catch(() => {});
    setView((v) => ({ ...v, circle: { ...v.circle, seenMonth: latestDraw.month } }));
  }, [view, latestDraw, circleId]);

  const header = (
    <AppBar
      onBack={back}
      title={view ? planById(view.circle.planId)?.title : "دوره"}
      sub={
        view && `سهم ماهانه ${formatCompact(view.circle.share)}، دریافت یک‌جا ${formatCompact(view.circle.pot)} تومان`
      }
    />
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

  if (circle.status === "forming" || circle.status === "expired") {
    return (
      <div className="home">
        {header}
        <WaitingRoom view={view} ops={view.ops} reload={load} onLeft={back} onRetry={back} />
      </div>
    );
  }

  const me = members.find((m) => m.isMe);
  const schedule = scheduleOf(circle.startedAt, circle.months);
  const current = circle.status === "active" ? schedule[circle.currentMonth - 1] : null;
  const paymentOf = new Map(contributions.map((c) => [c.month, c]));
  const recipientOf = new Map(draws.map((d) => [d.month, members.find((m) => m.id === d.winner)]));
  const payable = circle.owed + circle.dueNow;
  const thisMonthPaid = paymentOf.get(circle.currentMonth)?.status === "paid";

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

  let hero;
  if (circle.wonMonth && me) {
    hero = (
      <section className="hero">
        <Pattern />
        <div className="hero-label">
          <Trophy size={16} /> در ماه {formatNumber(circle.wonMonth)} برنده شدید
        </div>
        <div className="hero-figure">
          {Math.round(circle.pot).toLocaleString("fa-IR")}
          <small>تومان</small>
        </div>
        <p className="hero-sub">
          {circle.status === "completed"
            ? "دوره تمام شد. ممنون از همراهی‌تان."
            : `تا پایان دوره هر ماه ${formatCompact(circle.share)} تومان قسط می‌پردازید.`}
        </p>
      </section>
    );
  } else {
    hero = (
      <section className={`hero ${circle.owed ? "warn" : ""}`}>
        <Pattern />
        <div className="hero-label">
          <CalendarClock size={16} />
          {current ? `قرعه‌کشی بعدی: ${formatDay(current.drawAt)}` : "دوره تمام شده"}
        </div>
        <div className="hero-figure">
          {Math.round(circle.pot).toLocaleString("fa-IR")}
          <small>تومان</small>
        </div>
        <p className="hero-sub">
          {circle.owed
            ? `${formatCompact(circle.owed)} تومان بدهی دارید که دیجی‌پی ضمانت کرده؛ تا تسویه در قرعه شرکت داده نمی‌شوید.`
            : current
              ? `${formatNumber(daysUntil(current.drawAt))} روز مانده؛ ${formatNumber(
                  members.filter((m) => !m.wonMonth).length,
                )} نفر با شانس برابر در قرعه‌اند.`
              : ""}
        </p>
      </section>
    );
  }

  const stage = current && (Date.now() < current.dueAt ? 0 : Date.now() < current.drawAt ? 1 : 2);

  return (
    <div className="home">
      {header}
      <div className="page">
        {hero}

        {current && me && (
          <section className="card">
            <div className="section-title">
              <h2>
                <CreditCard size={17} /> قسط ماه {formatNumber(circle.currentMonth)}
              </h2>
              <PaymentBadge contribution={paymentOf.get(circle.currentMonth)} />
            </div>
            <ol className="due-steps">
              <li className={stage >= 0 ? "on" : ""}>
                <b>{formatDay(current.dueAt)}</b>
                <span>سررسید</span>
              </li>
              <li className={stage >= 1 ? "on" : ""}>
                <b>تا {formatDay(current.lastPayDay)}</b>
                <span>۵ روز مهلت پرداخت</span>
              </li>
              <li className={stage >= 2 ? "on" : ""}>
                <b>{formatDay(current.drawAt)}</b>
                <span>قرعه‌کشی</span>
              </li>
            </ol>
            <div className="split">
              <span className="muted small">
                {thisMonthPaid ? (
                  circle.wonMonth ? (
                    "قسط این ماه پرداخت شد. ممنون!"
                  ) : (
                    `پرداخت شد؛ در قرعه‌ی ${formatDay(current.drawAt)} شرکت دارید.`
                  )
                ) : (
                  <>
                    <Wallet size={13} style={{ verticalAlign: "-2px" }} /> اگر تا {formatDay(current.lastPayDay)} پرداخت
                    نکنید، روز {formatDay(current.drawAt)} از کیف پولتان کسر می‌شود.
                  </>
                )}
              </span>
              {payable > 0 && (
                <button className="btn primary" onClick={pay} disabled={paying}>
                  {paying ? <Spinner /> : <CreditCard size={17} />}
                  {stage === 0 && !circle.owed ? "پرداخت زودتر" : "پرداخت"} {formatCompact(payable)}
                </button>
              )}
            </div>
          </section>
        )}

        <section className="card flush">
          <div className="section-title padded">
            <h2>تقویم اقساط</h2>
            <span className="muted small">اول هر ماه قسط، روز ششم قرعه</span>
          </div>
          <ul className="installments">
            {schedule.map((s) => {
              const who = recipientOf.get(s.month);
              const now = circle.status === "active" && s.month === circle.currentMonth;
              return (
                <li key={s.month} className={`${now ? "now" : ""} ${who?.isMe ? "mine" : ""}`}>
                  <div className="inst-month">
                    <strong>ماه {formatNumber(s.month)}</strong>
                    <span>{s.month === 1 ? `شروع، ${formatDay(s.dueAt)}` : `سررسید ${formatDay(s.dueAt)}`}</span>
                  </div>
                  <div className="inst-who">
                    {who ? (
                      <>
                        {who.isMe && <Trophy size={13} />} {seatName(who)}
                      </>
                    ) : (
                      <span className="muted">قرعه {formatDay(s.drawAt)}</span>
                    )}
                  </div>
                  {me && <PaymentBadge contribution={paymentOf.get(s.month)} />}
                  {paymentOf.get(s.month)?.method && (
                    <span className="inst-method">{METHOD_LABEL[paymentOf.get(s.month).method]}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </section>

        <section className="card">
          <div className="section-title">
            <h2>اعضا</h2>
            <span className="muted small">فقط شماره‌ی جایگاه نمایش داده می‌شود</span>
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
          </div>
        </section>

        <section className="card">
          <div className="section-title">
            <h2>قرعه‌کشی شفاف</h2>
          </div>
          <p className="muted small" style={{ marginBottom: 12 }}>
            هیچ‌کس، حتی دیجی‌پی، نمی‌تواند برنده را انتخاب یا نتیجه را عوض کند:
          </p>
          <ul className="how-list fair-list">
            <li>
              <Lock size={18} />
              <span>
                <b>قفل از قبل.</b> پیش از شروع دوره، نتیجه‌ی همه‌ی قرعه‌ها با یک کلید قفل شد و اثر انگشت آن برای همه
                منتشر شد؛ مثل پاکت مهر و موم‌شده‌ای که دیگر نمی‌شود عوضش کرد.
              </span>
            </li>
            <li>
              <Smartphone size={18} />
              <span>
                <b>سهم گوشی شما.</b> گوشی هر عضو هنگام عضویت یک عدد تصادفی ساخت که در قرعه اثر دارد و دیجی‌پی از قبل
                نمی‌دانستش.
              </span>
            </li>
            <li>
              <BadgeCheck size={18} />
              <span>
                <b>خودتان بررسی کنید.</b> با دکمه‌ی «بررسی»، گوشی خودتان قرعه را از نو حساب می‌کند. اگر حتی یک رقم دست
                خورده باشد، معلوم می‌شود.
              </span>
            </li>
          </ul>

          {draws.length === 0 ? (
            <p className="muted small">هنوز قرعه‌ای انجام نشده.</p>
          ) : (
            <ul className="timeline">
              {[...draws].reverse().map((d) => (
                <DrawRow key={d.month} draw={d} members={members} digest={view.nonceDigest} onReplay={setReveal} />
              ))}
            </ul>
          )}

          <details className="tech">
            <summary>جزئیات فنی برای کنجکاوها</summary>
            <p>
              کلید قفل یک زنجیره‌ی هش SHA-256 است که فقط سرِ آن («اثر انگشت») از روز اول منتشر شده. هر قرعه حلقه‌ی بعدی
              زنجیره را آشکار می‌کند و برنده از <code dir="ltr">sha256(حلقه | کد تصادفی اعضا | ماه)</code> درمی‌آید.
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
          </details>
        </section>
      </div>

      {reveal && (
        <DrawReveal draw={reveal} members={members} digest={view.nonceDigest} onClose={() => setReveal(null)} />
      )}
    </div>
  );
}
