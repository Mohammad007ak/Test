import { useState } from "react";
import { duesForMonth, fundBalance, loanProgress, overdueDues, sum } from "../lib/fund.js";
import { copyText, formatMoney, formatNumber, reminderText, smsLink } from "../lib/format.js";
import { monthLabel } from "../lib/jalali.js";

export default function Dashboard({ state, currentMonth, goTo }) {
  const [copiedId, setCopiedId] = useState(null);
  const { fund, members, loans } = state;
  const balance = fundBalance(state);
  const thisMonth = duesForMonth(state, currentMonth);
  const collected = sum(thisMonth.filter((d) => d.paid));
  const expected = sum(thisMonth);
  const percent = expected ? Math.round((collected / expected) * 100) : 0;
  const activeLoans = loans.filter((l) => !loanProgress(state, l).done);

  const overdueByMember = new Map();
  for (const due of overdueDues(state, currentMonth)) {
    overdueByMember.set(due.memberId, (overdueByMember.get(due.memberId) ?? 0) + due.amount);
  }
  const lateMembers = members
    .filter((m) => overdueByMember.has(m.id))
    .map((m) => ({ member: m, amount: overdueByMember.get(m.id) }))
    .sort((a, b) => b.amount - a.amount);

  return (
    <div className="stack">
      <div className="stats">
        <div className="stat hero">
          <span>موجودی صندوق</span>
          <strong>{formatMoney(balance)}</strong>
          <small>
            {balance >= fund.loanAmount
              ? `کافی برای ${formatNumber(Math.floor(balance / fund.loanAmount))} وام`
              : `${formatMoney(fund.loanAmount - balance)} تا وام بعدی`}
          </small>
        </div>
        <div className="stat">
          <span>اعضا</span>
          <strong>{formatNumber(members.length)}</strong>
          <small>{formatNumber(sum(members, (m) => m.shares))} سهم</small>
        </div>
        <div className="stat">
          <span>وام‌های فعال</span>
          <strong>{formatNumber(activeLoans.length)}</strong>
          <small>{formatMoney(sum(activeLoans, (l) => loanProgress(state, l).remaining))} مانده</small>
        </div>
        <div className={`stat ${lateMembers.length ? "warn" : ""}`}>
          <span>معوقات</span>
          <strong>{formatMoney(sum(lateMembers))}</strong>
          <small>{formatNumber(lateMembers.length)} نفر</small>
        </div>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>وصولی {monthLabel(currentMonth)}</h2>
          <button className="btn ghost" onClick={() => goTo("payments")}>
            ثبت پرداخت‌ها ←
          </button>
        </div>
        <div className="progress">
          <div style={{ width: `${percent}%` }} />
        </div>
        <p className="muted">
          {formatMoney(collected)} از {formatMoney(expected)} ({formatNumber(percent)}٪) ·{" "}
          {formatNumber(thisMonth.filter((d) => !d.paid).length)} پرداخت مانده
        </p>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>بدهکارها</h2>
        </div>
        {lateMembers.length === 0 ? (
          <p className="empty">همه به‌روز هستند 🎉</p>
        ) : (
          <ul className="list">
            {lateMembers.map(({ member, amount }) => {
              const text = reminderText(fund.name, member.name, amount);
              return (
                <li key={member.id}>
                  <div>
                    <strong>{member.name}</strong>
                    <span className="danger">{formatMoney(amount)}</span>
                  </div>
                  <div className="row-actions">
                    {member.phone && (
                      <a className="btn small" href={smsLink(member.phone, text)}>
                        پیامک یادآوری
                      </a>
                    )}
                    <button
                      className="btn small ghost"
                      onClick={async () => {
                        if (await copyText(text)) setCopiedId(member.id);
                      }}
                    >
                      {copiedId === member.id ? "کپی شد ✓" : "کپی متن"}
                    </button>
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
