import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { formatMoney, formatNumber } from "../lib/format.js";
import { addMonths, formatDate, monthLabel } from "../lib/jalali.js";

const DRAW_STATUS = {
  confirmed: { label: "نهایی شد", className: "tag" },
  cancelled: { label: "لغو شد", className: "tag danger" },
  pending: { label: "در انتظار تأیید", className: "tag muted-tag" },
};

export default function MemberView({ fundId, back }) {
  const [view, setView] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api("GET", `/api/funds/${fundId}/view`).then(setView, setError);
  }, [fundId]);

  if (error) return <p className="danger">{error.message}</p>;
  if (!view) return <p className="empty">در حال بارگذاری…</p>;

  const { fund, me } = view;
  const dueNow = me?.dues.filter((d) => !d.paid && d.month === view.currentMonth) ?? [];

  return (
    <div className="stack">
      <header className="topbar">
        <div>
          <h1>{fund.name}</h1>
          <span className="muted">
            {view.isManager ? "پیش‌نمایش صفحه‌ی اعضا" : `سلام ${me?.name ?? ""} 👋`}
          </span>
        </div>
        <button className="btn ghost small" onClick={() => back(view.isManager)}>
          → بازگشت
        </button>
      </header>

      {me && (
        <div className="stats">
          <div className={`stat hero ${me.overdueAmount ? "hero-warn" : ""}`}>
            <span>وضعیت شما</span>
            <strong>{me.overdueAmount ? `${formatMoney(me.overdueAmount)} معوق` : "همه‌چیز پرداخت شده ✓"}</strong>
            <small>
              {dueNow.length
                ? `پرداخت این ماه: ${formatMoney(dueNow.reduce((t, d) => t + d.amount, 0))}`
                : `${formatNumber(me.shares)} سهم، ماهی ${formatMoney(me.shares * fund.contribution)}`}
            </small>
          </div>
        </div>
      )}

      {me?.loans.map((loan, i) => (
        <section className="card" key={i}>
          <div className="card-head">
            <h2>وام شما</h2>
            {loan.done ? <span className="tag">تسویه شد ✓</span> : <span className="tag">فعال</span>}
          </div>
          <div className="progress">
            <div style={{ width: `${Math.round((loan.paidCount / loan.installments) * 100)}%` }} />
          </div>
          <p className="muted">
            {formatMoney(loan.amount)}، {formatNumber(loan.paidCount)} از {formatNumber(loan.installments)} قسط
            پرداخت شده، مانده {formatMoney(loan.remaining)}، قسط آخر{" "}
            {monthLabel(addMonths(loan.firstInstallmentMonth, loan.installments - 1))}
          </p>
        </section>
      ))}

      {me && (
        <section className="card">
          <div className="card-head">
            <h2>پرداخت‌های شما</h2>
          </div>
          <ul className="list compact">
            {me.dues.slice(0, 12).map((due) => (
              <li key={due.month + due.type}>
                <div>
                  <strong>{monthLabel(due.month)}</strong>
                  <span className="muted">{due.type === "contribution" ? "سهم ماهانه" : "قسط وام"}</span>
                </div>
                <div className="due-status">
                  <span>{formatMoney(due.amount)}</span>
                  {due.paid ? (
                    <span className="tag">پرداخت شد</span>
                  ) : due.month < view.currentMonth ? (
                    <span className="tag danger">معوق</span>
                  ) : (
                    <span className="tag muted-tag">این ماه</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <div className="card-head">
          <h2>شفافیت صندوق</h2>
        </div>
        <div className="facts">
          <div>
            <span>موجودی</span>
            <strong>{formatMoney(view.balance)}</strong>
          </div>
          <div>
            <span>اعضا</span>
            <strong>
              {formatNumber(view.memberCount)} نفر، {formatNumber(view.totalShares)} سهم
            </strong>
          </div>
          <div>
            <span>مبلغ هر وام</span>
            <strong>{formatMoney(fund.loanAmount)}</strong>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>سابقه‌ی قرعه‌کشی‌ها</h2>
        </div>
        <p className="muted">
          هر قرعه‌کشی روی سرور انجام و ثبت می‌شود و مدیر نمی‌تواند آن را پاک کند. اگر قرعه‌ای لغو و دوباره
          انجام شده باشد، اینجا دیده می‌شود.
        </p>
        {view.draws.length === 0 ? (
          <p className="empty">هنوز قرعه‌کشی آنلاین انجام نشده.</p>
        ) : (
          <ul className="list compact">
            {view.draws.map((draw, i) => (
              <li key={i}>
                <div>
                  <strong>{draw.winnerName}</strong>
                  <span className="muted">
                    {monthLabel(draw.month)}، {formatDate(new Date(draw.createdAt).toISOString())}
                  </span>
                </div>
                <span className={DRAW_STATUS[draw.status].className}>{DRAW_STATUS[draw.status].label}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h2>وام‌های داده‌شده</h2>
        </div>
        {view.loans.length === 0 ? (
          <p className="empty">هنوز وامی داده نشده.</p>
        ) : (
          <ul className="list compact">
            {view.loans.map((loan, i) => (
              <li key={i}>
                <div>
                  <strong>{loan.memberName}</strong>
                  <span className="muted">{monthLabel(loan.drawMonth)}</span>
                </div>
                <div className="due-status">
                  <span>{formatMoney(loan.amount)}</span>
                  {loan.viaDraw ? (
                    <span className="tag">با قرعه‌کشی آنلاین</span>
                  ) : (
                    <span className="tag muted-tag">ثبت دستی</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
