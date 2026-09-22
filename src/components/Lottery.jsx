import { useEffect, useRef, useState } from "react";
import { fundBalance, lotteryEntries } from "../lib/fund.js";
import { api } from "../lib/api.js";
import { formatMoney, formatNumber } from "../lib/format.js";
import { monthLabel } from "../lib/jalali.js";

const SPIN_MS = 3000;

export default function Lottery({ state, update, currentMonth, server }) {
  const { fund, loans, members } = state;
  const entries = lotteryEntries(state);
  const balance = fundBalance(state);
  const enoughMoney = balance >= fund.loanAmount;
  const drawnThisMonth = loans.some((l) => l.drawMonth === currentMonth);
  const memberById = new Map(members.map((m) => [m.id, m]));

  const [spinning, setSpinning] = useState(false);
  const [shown, setShown] = useState(null);
  const [winner, setWinner] = useState(null);
  const [drawId, setDrawId] = useState(null);
  const [busy, setBusy] = useState(false);
  const timers = useRef([]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const reset = () => {
    setWinner(null);
    setShown(null);
    setDrawId(null);
  };

  // The server picks the winner; the animation only reveals it.
  const draw = async () => {
    if (drawnThisMonth && !confirm("این ماه قبلاً قرعه‌کشی شده. قرعه‌ی دیگری انجام شود؟")) return;
    setBusy(true);
    let result;
    try {
      await server.flush();
      result = await api("POST", `/api/funds/${server.fundId}/draws`);
    } catch (e) {
      alert(e.message);
      return;
    } finally {
      setBusy(false);
    }
    const chosen = memberById.get(result.draw.winnerId) ?? { id: result.draw.winnerId, name: result.draw.winnerName };
    setDrawId(result.draw.id);
    setWinner(null);
    setSpinning(true);

    // Flash names with a slowing rhythm before landing on the winner.
    let elapsed = 0;
    let delay = 60;
    const names = entries.map((e) => e.member);
    let i = 0;
    while (elapsed < SPIN_MS) {
      const member = names[i++ % names.length];
      timers.current.push(setTimeout(() => setShown(member), elapsed));
      elapsed += delay;
      delay *= 1.08;
    }
    timers.current.push(
      setTimeout(() => {
        setShown(chosen);
        setWinner(chosen);
        setSpinning(false);
      }, elapsed),
    );
  };

  const resolve = async (action) => {
    if (action === "cancel" && !confirm("قرعه لغو شود؟ لغو قرعه در سابقه ثبت می‌شود و اعضا آن را می‌بینند.")) return;
    setBusy(true);
    try {
      const result = await api("POST", `/api/funds/${server.fundId}/draws/${drawId}/${action}`);
      if (action === "confirm") server.applyServer(result.data, result.version);
      reset();
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const startNewCycle = () => {
    if (confirm("دور جدید شروع شود؟ همه‌ی اعضا دوباره در قرعه‌کشی شرکت می‌کنند.")) {
      update((s) => ({ ...s, fund: { ...s.fund, cycle: s.fund.cycle + 1 } }));
    }
  };

  const history = [...loans].sort((a, b) => b.drawMonth.localeCompare(a.drawMonth) || b.createdAt.localeCompare(a.createdAt));

  return (
    <div className="stack">
      <section className="card lottery">
        <div className="card-head">
          <h2>قرعه‌کشی {monthLabel(currentMonth)}</h2>
          <span className="tag">دور {formatNumber(fund.cycle)}</span>
        </div>

        <div className={`draw-stage ${spinning ? "spinning" : ""} ${winner ? "won" : ""}`}>
          {shown ? (
            <>
              <span className="draw-name">{shown.name}</span>
              {winner && <span className="draw-sub">برنده‌ی وام {formatMoney(fund.loanAmount)} 🎉</span>}
            </>
          ) : (
            <span className="draw-hint">
              {entries.length ? "آماده‌ی قرعه‌کشی" : "همه‌ی اعضا در این دور وام گرفته‌اند"}
            </span>
          )}
        </div>

        {winner ? (
          <div className="row-actions center">
            <button className="btn primary" onClick={() => resolve("confirm")} disabled={busy}>
              ثبت وام برای {winner.name}
            </button>
            <button className="btn ghost" onClick={() => resolve("cancel")} disabled={busy}>
              لغو قرعه
            </button>
          </div>
        ) : entries.length ? (
          <>
            <button className="btn primary big" onClick={draw} disabled={busy || spinning || !enoughMoney}>
              {spinning ? "در حال قرعه‌کشی…" : "🎲 شروع قرعه‌کشی"}
            </button>
            {!enoughMoney && (
              <p className="danger center">
                موجودی صندوق ({formatMoney(balance)}) برای یک وام {formatMoney(fund.loanAmount)} کافی نیست.
              </p>
            )}
          </>
        ) : (
          <button className="btn primary big" onClick={startNewCycle}>
            شروع دور جدید
          </button>
        )}

        {entries.length > 0 && (
          <div className="entries">
            <p className="muted">
              قرعه روی سرور انجام می‌شود و همه‌ی قرعه‌ها، حتی لغوشده‌ها، برای اعضا ثبت می‌شود.
            </p>
            <p className="muted">
              شرکت‌کننده‌ها (هر سهم = یک شانس)، {formatNumber(entries.length)} نفر
            </p>
            <div className="chips">
              {entries.map(({ member, tickets }) => (
                <span key={member.id} className={`chip ${shown?.id === member.id ? "active" : ""}`}>
                  {member.name}
                  {tickets > 1 && <b>×{formatNumber(tickets)}</b>}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h2>سابقه‌ی قرعه‌ها</h2>
        </div>
        {history.length === 0 ? (
          <p className="empty">هنوز قرعه‌کشی نشده.</p>
        ) : (
          <ul className="list">
            {history.map((loan) => (
              <li key={loan.id}>
                <div>
                  <strong>{memberById.get(loan.memberId)?.name ?? "عضو حذف‌شده"}</strong>
                  <span className="muted">{monthLabel(loan.drawMonth)}</span>
                </div>
                <span>{formatMoney(loan.amount)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
