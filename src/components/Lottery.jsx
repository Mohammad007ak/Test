import { useEffect, useMemo, useRef, useState } from "react";
import { Ban, Dices, RotateCcw, ShieldCheck, Ticket, Trophy } from "lucide-react";
import Pattern from "../ui/Pattern.jsx";
import { Avatar, Money, Spinner } from "../ui/bits.jsx";
import { useDialog, useToast } from "../ui/feedback.jsx";
import { api } from "../lib/api.js";
import { fundBalance, lotteryEntries, sum } from "../lib/fund.js";
import { formatCompact, formatNumber } from "../lib/format.js";
import { monthLabel } from "../lib/jalali.js";

const ITEM = 76;
const SPIN_MS = 4200;
const CONFETTI = ["#ffc53d", "#ffd66e", "#5c6bff", "#ffffff", "#0000ff"];

function Confetti() {
  const pieces = useMemo(
    () =>
      Array.from({ length: 36 }, (_, i) => {
        const angle = (Math.PI * 2 * i) / 36 + Math.random() * 0.3;
        const dist = 120 + Math.random() * 140;
        return {
          x: `${Math.cos(angle) * dist}px`,
          y: `${Math.sin(angle) * dist - 40}px`,
          r: `${Math.random() * 720 - 360}deg`,
          color: CONFETTI[i % CONFETTI.length],
          delay: `${Math.random() * 0.15}s`,
        };
      }),
    [],
  );
  return (
    <div className="confetti" aria-hidden="true">
      {pieces.map((p, i) => (
        <i key={i} style={{ "--x": p.x, "--y": p.y, "--r": p.r, background: p.color, animationDelay: p.delay }} />
      ))}
    </div>
  );
}

export default function Lottery({ state, update, currentMonth, server }) {
  const { fund, loans, members } = state;
  const entries = lotteryEntries(state);
  const balance = fundBalance(state);
  const enoughMoney = balance >= fund.loanAmount;
  const memberById = new Map(members.map((m) => [m.id, m]));
  const toast = useToast();
  const confirm = useDialog();

  const [phase, setPhase] = useState("idle"); // idle | spinning | won
  const [reel, setReel] = useState([]);
  const [offset, setOffset] = useState(0);
  const [winner, setWinner] = useState(null);
  const [drawId, setDrawId] = useState(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const draw = async () => {
    if (loans.some((l) => l.drawMonth === currentMonth)) {
      const ok = await confirm({
        title: "قرعه‌ی دوم در این ماه؟",
        body: "این ماه یک وام با قرعه داده شده. اگر موجودی کافی است می‌توانید قرعه‌ی دیگری بکشید.",
        confirmLabel: "قرعه‌ی بعدی",
        tone: "gold",
      });
      if (!ok) return;
    }
    setBusy(true);
    let result;
    try {
      await server.flush();
      result = await api("POST", `/api/funds/${server.fundId}/draws`);
    } catch (e) {
      toast(e.message, { tone: "error" });
      setBusy(false);
      return;
    }
    setBusy(false);

    // The server has already chosen; the reel only reveals it.
    const chosen = memberById.get(result.draw.winnerId) ?? { id: result.draw.winnerId, name: result.draw.winnerName };
    const names = entries.map((e) => e.member);
    const strip = [];
    for (let i = 0; i < 28; i++) strip.push(names[(i * 7 + 3) % names.length]);
    strip.push(chosen, names[0]);
    setReel(strip);
    setOffset(0);
    setWinner(null);
    setDrawId(result.draw.id);
    setPhase("spinning");
    requestAnimationFrame(() => requestAnimationFrame(() => setOffset((strip.length - 2) * ITEM)));
    timer.current = setTimeout(() => {
      setWinner(chosen);
      setPhase("won");
    }, SPIN_MS);
  };

  const reset = () => {
    setPhase("idle");
    setWinner(null);
    setDrawId(null);
    setReel([]);
  };

  const resolve = async (action) => {
    if (action === "cancel") {
      const ok = await confirm({
        title: "لغو این قرعه؟",
        body: "لغو قرعه در سابقه ثبت می‌شود و همه‌ی اعضا آن را می‌بینند.",
        confirmLabel: "لغو قرعه",
        tone: "danger",
      });
      if (!ok) return;
    }
    setBusy(true);
    try {
      const result = await api("POST", `/api/funds/${server.fundId}/draws/${drawId}/${action}`);
      if (action === "confirm") {
        server.applyServer(result.data, result.version);
        toast(`وام ${winner.name} ثبت شد`);
      } else {
        toast("قرعه لغو شد");
      }
      reset();
    } catch (e) {
      toast(e.message, { tone: "error" });
    } finally {
      setBusy(false);
    }
  };

  const startNewCycle = async () => {
    const ok = await confirm({
      title: "شروع دور جدید",
      body: "همه‌ی اعضا در این دور وام گرفته‌اند. با شروع دور جدید، همه دوباره در قرعه‌کشی شرکت می‌کنند.",
      confirmLabel: "شروع دور جدید",
    });
    if (ok) update((s) => ({ ...s, fund: { ...s.fund, cycle: s.fund.cycle + 1 } }));
  };

  const history = [...loans].sort((a, b) => b.drawMonth.localeCompare(a.drawMonth));
  const totalTickets = sum(entries, (e) => e.tickets);

  return (
    <div className="page">
      <section className={`stage ${phase === "won" ? "won" : ""}`}>
        <Pattern />
        {phase === "won" && <Confetti key={drawId} />}
        <div className="stage-kicker">
          <Dices size={16} /> قرعه‌کشی {monthLabel(currentMonth)}، دور {formatNumber(fund.cycle)}
        </div>

        <div className="reel-window" aria-live="polite">
          {phase === "idle" ? (
            <div className="reel-idle">
              {entries.length ? `${formatNumber(totalTickets)} شانس از ${formatNumber(entries.length)} نفر` : "همه در این دور وام گرفته‌اند"}
            </div>
          ) : (
            <div
              className="reel"
              style={{
                transform: `translateY(-${offset}px)`,
                transition: phase === "spinning" && offset ? `transform ${SPIN_MS}ms cubic-bezier(0.12, 0.8, 0.14, 1)` : "none",
              }}
            >
              {reel.map((m, i) => (
                <span key={i}>{m.name}</span>
              ))}
            </div>
          )}
        </div>

        <p className="stage-caption">
          {phase === "won"
            ? `برنده‌ی وام ${formatCompact(fund.loanAmount)} تومانی 🎉`
            : phase === "spinning"
              ? "در حال قرعه‌کشی…"
              : enoughMoney
                ? `وام این دور: ${formatCompact(fund.loanAmount)} تومان`
                : `موجودی ${formatCompact(balance)} تومان است؛ برای وام ${formatCompact(fund.loanAmount)} تومانی کافی نیست`}
        </p>

        {phase === "won" ? (
          <div className="row-actions" style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
            <button className="btn gold lg" onClick={() => resolve("confirm")} disabled={busy}>
              {busy ? <Spinner /> : <Trophy size={18} />} ثبت وام برای {winner.name}
            </button>
            <button className="btn lg" style={{ background: "rgb(255 255 255 / 0.1)", color: "#fff" }} onClick={() => resolve("cancel")} disabled={busy}>
              <Ban size={18} /> لغو
            </button>
          </div>
        ) : entries.length ? (
          <button className="btn gold lg" onClick={draw} disabled={busy || phase === "spinning" || !enoughMoney}>
            {busy ? <Spinner /> : <Dices size={20} />} شروع قرعه‌کشی
          </button>
        ) : (
          <button className="btn gold lg" onClick={startNewCycle}>
            <RotateCcw size={18} /> شروع دور جدید
          </button>
        )}
      </section>

      <div className="inline-note">
        <ShieldCheck size={18} />
        <span>
          برنده را سرور با عدد تصادفی امن انتخاب می‌کند. هر قرعه، حتی قرعه‌های لغوشده، ثبت می‌شود و اعضا در صفحه‌ی خودشان می‌بینند.
        </span>
      </div>

      {entries.length > 0 && (
        <section className="card">
          <div className="section-title">
            <h2>شرکت‌کننده‌ها</h2>
            <span className="muted">هر سهم یک شانس</span>
          </div>
          <div className="tickets">
            {entries.map(({ member, tickets }) => (
              <span key={member.id} className={`ticket ${winner?.id === member.id ? "lit" : ""}`}>
                <Avatar name={member.name} id={member.id} size="sm" />
                {member.name}
                {tickets > 1 && (
                  <b>
                    <Ticket size={12} style={{ verticalAlign: "-1px" }} /> ×{formatNumber(tickets)}
                  </b>
                )}
              </span>
            ))}
          </div>
        </section>
      )}

      <section className="card">
        <div className="section-title">
          <h2>برنده‌های قبلی</h2>
        </div>
        {history.length === 0 ? (
          <p className="muted small">هنوز وامی داده نشده.</p>
        ) : (
          <ul className="timeline">
            {history.map((loan) => (
              <li key={loan.id}>
                <span className={`dot ${loan.drawId ? "" : "manual"}`}>
                  <Trophy size={15} />
                </span>
                <div className="t-body">
                  <div>
                    <strong>{memberById.get(loan.memberId)?.name ?? "عضو سابق"}</strong>
                    <span>
                      {monthLabel(loan.drawMonth)}، {loan.drawId ? "با قرعه‌کشی آنلاین" : "ثبت دستی"}
                    </span>
                  </div>
                  <Money amount={loan.amount} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
