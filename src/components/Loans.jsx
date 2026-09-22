import { loanProgress } from "../lib/fund.js";
import { formatMoney, formatNumber } from "../lib/format.js";
import { addMonths, monthLabel } from "../lib/jalali.js";

export default function Loans({ state }) {
  const memberById = new Map(state.members.map((m) => [m.id, m]));
  const loans = state.loans
    .map((loan) => ({ loan, progress: loanProgress(state, loan) }))
    .sort((a, b) => a.progress.done - b.progress.done || b.loan.drawMonth.localeCompare(a.loan.drawMonth));

  return (
    <div className="stack">
      <section className="card">
        <div className="card-head">
          <h2>وام‌ها ({formatNumber(loans.length)})</h2>
        </div>
        {loans.length === 0 ? (
          <p className="empty">هنوز وامی داده نشده. از بخش قرعه‌کشی شروع کنید.</p>
        ) : (
          <ul className="list">
            {loans.map(({ loan, progress }) => {
              const percent = Math.round((progress.paidCount / loan.installments) * 100);
              return (
                <li key={loan.id} className="loan">
                  <div>
                    <strong>{memberById.get(loan.memberId)?.name ?? "عضو حذف‌شده"}</strong>
                    {progress.done ? <span className="tag">تسویه شد ✓</span> : <span className="tag">فعال</span>}
                  </div>
                  <div className="muted">
                    {formatMoney(loan.amount)}، {formatNumber(loan.installments)} قسط از{" "}
                    {monthLabel(loan.firstInstallmentMonth)} تا{" "}
                    {monthLabel(addMonths(loan.firstInstallmentMonth, loan.installments - 1))}
                  </div>
                  <div className="progress">
                    <div style={{ width: `${percent}%` }} />
                  </div>
                  <div className="muted">
                    {formatNumber(progress.paidCount)} از {formatNumber(loan.installments)} قسط پرداخت شده،
                    مانده: {formatMoney(progress.remaining)}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
