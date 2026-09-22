import { useState } from "react";
import { Landmark } from "lucide-react";
import { Avatar, EmptyState, Money, Ring, Segmented } from "../ui/bits.jsx";
import { installmentAmount, loanProgress, matchesDue } from "../lib/fund.js";
import { formatCompact, formatNumber } from "../lib/format.js";
import { addMonths, monthLabel } from "../lib/jalali.js";

function scheduleFor(state, loan, currentMonth) {
  return Array.from({ length: loan.installments }, (_, i) => {
    const month = addMonths(loan.firstInstallmentMonth, i);
    const due = { memberId: loan.memberId, type: "installment", loanId: loan.id, month };
    const paid = state.payments.some((p) => matchesDue(p, due));
    const status = paid ? "paid" : month < currentMonth ? "late" : month === currentMonth ? "now" : "";
    return { month, status, amount: installmentAmount(loan, i) };
  });
}

export default function Loans({ state, currentMonth, openMember }) {
  const [filter, setFilter] = useState("active");
  const memberById = new Map(state.members.map((m) => [m.id, m]));
  const all = state.loans
    .map((loan) => ({ loan, progress: loanProgress(state, loan) }))
    .sort((a, b) => b.loan.drawMonth.localeCompare(a.loan.drawMonth));
  const active = all.filter((l) => !l.progress.done);
  const shown = filter === "active" ? active : all.filter((l) => l.progress.done);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>وام‌ها</h1>
          <p>
            {formatCompact(active.reduce((t, l) => t + l.progress.remaining, 0))} تومان در دست اعضاست
          </p>
        </div>
        <Segmented
          value={filter}
          onChange={setFilter}
          options={[
            { value: "active", label: "فعال", count: active.length },
            { value: "done", label: "تسویه‌شده", count: all.length - active.length },
          ]}
        />
      </div>

      {shown.length === 0 ? (
        <section className="card">
          <EmptyState
            icon={Landmark}
            title={filter === "active" ? "وام فعالی نیست" : "هنوز وامی تسویه نشده"}
            text={filter === "active" ? "بعد از قرعه‌کشی، وام برنده اینجا دنبال می‌شود." : undefined}
          />
        </section>
      ) : (
        shown.map(({ loan, progress }) => {
          const member = memberById.get(loan.memberId);
          const schedule = scheduleFor(state, loan, currentMonth);
          const late = schedule.filter((s) => s.status === "late");
          const next = schedule.find((s) => s.status !== "paid");
          return (
            <section key={loan.id} className="card">
              <div className="loan-top">
                <button className="avatar-btn" onClick={() => member && openMember(member.id)}>
                  <Avatar name={member?.name ?? "؟"} id={loan.memberId} />
                </button>
                <div>
                  <strong>{member?.name ?? "عضو سابق"}</strong>
                  <span className="muted small">
                    وام {monthLabel(loan.drawMonth)}، <Money amount={loan.amount} />
                  </span>
                </div>
                <Ring
                  value={progress.paidCount / loan.installments}
                  size={58}
                  done={progress.done}
                  label={<span dir="ltr">{`${formatNumber(progress.paidCount)}/${formatNumber(loan.installments)}`}</span>}
                />
              </div>

              <div className="schedule" aria-label="جدول اقساط">
                {schedule.map((s) => (
                  <i key={s.month} className={s.status} title={`${monthLabel(s.month)}، ${formatCompact(s.amount)} تومان`} />
                ))}
              </div>

              <div className="loan-foot">
                <span>مانده: {formatCompact(progress.remaining)} تومان</span>
                {progress.done ? (
                  <span className="badge success">تسویه شد</span>
                ) : late.length ? (
                  <span className="badge danger">{formatNumber(late.length)} قسط عقب</span>
                ) : (
                  next && (
                    <span>
                      قسط بعدی {monthLabel(next.month)}، {formatCompact(next.amount)}
                    </span>
                  )
                )}
              </div>
            </section>
          );
        })
      )}

      {shown.length > 0 && (
        <div className="legend">
          <span>
            <i className="paid" /> پرداخت‌شده
          </span>
          <span>
            <i className="now" /> این ماه
          </span>
          <span>
            <i className="late" /> عقب‌افتاده
          </span>
          <span>
            <i /> آینده
          </span>
        </div>
      )}
    </div>
  );
}
