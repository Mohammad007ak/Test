import { useState } from "react";
import { MonthPicker } from "./inputs.jsx";
import { duesForMonth, matchesDue, paymentForDue, sum } from "../lib/fund.js";
import { formatMoney, formatNumber } from "../lib/format.js";
import { monthLabel } from "../lib/jalali.js";

export default function Payments({ state, update, currentMonth }) {
  const [month, setMonth] = useState(currentMonth);
  const dues = duesForMonth(state, month);

  const toggle = (due) => {
    update((s) => ({
      ...s,
      payments: due.paid
        ? s.payments.filter((p) => !matchesDue(p, due))
        : [...s.payments, paymentForDue(due)],
    }));
  };

  const markAllPaid = () => {
    const unpaid = dues.filter((d) => !d.paid);
    if (!unpaid.length || !confirm(`${formatNumber(unpaid.length)} پرداخت به‌عنوان «پرداخت‌شده» ثبت شود؟`)) return;
    update((s) => ({
      ...s,
      payments: [...s.payments, ...unpaid.map(paymentForDue)],
    }));
  };

  const rows = state.members
    .map((member) => ({
      member,
      dues: dues.filter((d) => d.memberId === member.id),
    }))
    .filter((row) => row.dues.length > 0);

  return (
    <div className="stack">
      <section className="card">
        <div className="card-head">
          <h2>پرداخت‌های {monthLabel(month)}</h2>
          <MonthPicker value={month} onChange={setMonth} />
        </div>
        <p className="muted">
          وصول‌شده {formatMoney(sum(dues.filter((d) => d.paid)))} از {formatMoney(sum(dues))}، روی هر
          مورد بزنید تا پرداخت‌شده یا پرداخت‌نشده شود.
        </p>

        {rows.length === 0 ? (
          <p className="empty">برای این ماه پرداختی تعریف نشده.</p>
        ) : (
          <ul className="list">
            {rows.map(({ member, dues: memberDues }) => (
              <li key={member.id}>
                <div>
                  <strong>{member.name}</strong>
                </div>
                <div className="row-actions">
                  {memberDues.map((due) => (
                    <button
                      key={due.type + (due.loanId ?? "")}
                      className={`pay-chip ${due.paid ? "paid" : month < currentMonth ? "late" : ""}`}
                      onClick={() => toggle(due)}
                    >
                      <span>{due.type === "contribution" ? "سهم ماهانه" : "قسط وام"}</span>
                      <b>{formatMoney(due.amount)}</b>
                      <i>{due.paid ? "✓ پرداخت شد" : "پرداخت نشده"}</i>
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}

        {dues.some((d) => !d.paid) && (
          <button className="btn ghost wide" onClick={markAllPaid}>
            همه‌ی موارد این ماه پرداخت شد
          </button>
        )}
      </section>
    </div>
  );
}
