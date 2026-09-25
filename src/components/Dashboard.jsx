import {
  AlertCircle,
  CalendarCheck,
  Copy,
  Dices,
  MessageSquareText,
  UserPlus,
  Wallet,
  WalletCards,
} from "lucide-react";
import Pattern from "../ui/Pattern.jsx";
import CollectionChart from "./CollectionChart.jsx";
import { AnimatedNumber, Avatar, EmptyState, Money, Ring } from "../ui/bits.jsx";
import { useToast } from "../ui/feedback.jsx";
import { duesForMonth, fundBalance, loanProgress, overdueDues, sum } from "../lib/fund.js";
import { copyText, formatCompact, formatNumber, reminderText, smsLink } from "../lib/format.js";
import { formatDate, monthLabel } from "../lib/jalali.js";

export default function Dashboard({ state, currentMonth, goTo, openMember }) {
  const toast = useToast();
  const { fund, members, loans, payments } = state;
  const balance = fundBalance(state);
  const loansAvailable = Math.floor(Math.max(0, balance) / fund.loanAmount);
  const towardNext = Math.max(0, balance) % fund.loanAmount;

  const thisMonth = duesForMonth(state, currentMonth);
  const collected = sum(thisMonth.filter((d) => d.paid));
  const expected = sum(thisMonth);
  const activeLoans = loans.filter((l) => !loanProgress(state, l).done);

  const overdueByMember = new Map();
  for (const due of overdueDues(state, currentMonth)) {
    const entry = overdueByMember.get(due.memberId) ?? { amount: 0, months: new Set() };
    entry.amount += due.amount;
    entry.months.add(due.month);
    overdueByMember.set(due.memberId, entry);
  }
  const late = members
    .filter((m) => overdueByMember.has(m.id))
    .map((m) => ({ member: m, ...overdueByMember.get(m.id) }))
    .sort((a, b) => b.amount - a.amount);

  const memberName = new Map(members.map((m) => [m.id, m.name]));
  const recent = payments
    .filter((p) => p.paidAt)
    .sort((a, b) => b.paidAt.localeCompare(a.paidAt))
    .slice(0, 5);

  const copyReminder = async (member, amount) => {
    if (await copyText(reminderText(fund, member.name, amount))) toast("متن یادآوری کپی شد");
  };

  return (
    <div className="page">
      <section className="hero">
        <Pattern />
        <div className="hero-label">
          <Wallet size={16} /> موجودی صندوق
        </div>
        <div className="hero-figure">
          <AnimatedNumber value={balance} />
          <small>تومان</small>
        </div>
        <p className="hero-sub">
          {loansAvailable > 0
            ? `آماده‌ی پرداخت ${formatNumber(loansAvailable)} وام ${formatCompact(fund.loanAmount)} تومانی`
            : "هنوز به مبلغ یک وام نرسیده"}
        </p>
        <div className="hero-meter">
          <div className="track">
            <div className="fill" style={{ width: `${(towardNext / fund.loanAmount) * 100}%` }} />
          </div>
          <div className="labels">
            <span>تا وام بعدی</span>
            <span>
              {formatCompact(towardNext)} از {formatCompact(fund.loanAmount)}
            </span>
          </div>
        </div>
      </section>

      <div className="quick">
        <button onClick={() => goTo("payments")}>
          <span className="q-icon">
            <CalendarCheck size={22} />
          </span>
          ثبت پرداخت
        </button>
        <button onClick={() => goTo("lottery")}>
          <span className="q-icon">
            <Dices size={22} />
          </span>
          قرعه‌کشی
        </button>
        <button onClick={() => goTo("members", { add: true })}>
          <span className="q-icon">
            <UserPlus size={22} />
          </span>
          عضو جدید
        </button>
        <button onClick={() => goTo("loans")}>
          <span className="q-icon">
            <WalletCards size={22} />
          </span>
          وام‌ها
        </button>
      </div>

      <div className="grid-2">
        <section className="card">
          <div className="section-title">
            <h2>وصولی {monthLabel(currentMonth)}</h2>
            <button className="link-btn small" onClick={() => goTo("payments")}>
              جزئیات
            </button>
          </div>
          <div className="split">
            <div className="stack-sm">
              <Money amount={collected} />
              <span className="muted small">
                از {formatCompact(expected)} تومان، {formatNumber(thisMonth.filter((d) => !d.paid).length)} پرداخت مانده
              </span>
            </div>
            <Ring value={expected ? collected / expected : 0} size={64} done={expected > 0 && collected >= expected} />
          </div>
        </section>

        <section className="card">
          <div className="section-title">
            <h2>روند وصول</h2>
            <span className="muted">شش ماه اخیر</span>
          </div>
          <CollectionChart state={state} currentMonth={currentMonth} />
        </section>
      </div>

      <div className="kpis">
        <div className="kpi">
          <span>اعضا</span>
          <strong>{formatNumber(members.length)}</strong>
          <small>{formatNumber(sum(members, (m) => m.shares))} سهم</small>
        </div>
        <div className="kpi">
          <span>وام‌های فعال</span>
          <strong>{formatNumber(activeLoans.length)}</strong>
          <small>{formatCompact(sum(activeLoans, (l) => loanProgress(state, l).remaining))} تومان مانده</small>
        </div>
        <div className="kpi">
          <span>معوقات</span>
          <strong className={late.length ? "danger" : ""}>{formatCompact(sum(late))}</strong>
          <small>{late.length ? `${formatNumber(late.length)} نفر` : "همه به‌روزند"}</small>
        </div>
      </div>

      <section className="card flush">
        <div className="section-title">
          <h2>بدهکارها</h2>
          {late.length > 0 && <span className="badge danger">{formatNumber(late.length)} نفر</span>}
        </div>
        {late.length === 0 ? (
          <EmptyState title="همه به‌روزند" text="هیچ پرداخت عقب‌افتاده‌ای وجود ندارد." />
        ) : (
          <ul className="rows">
            {late.map(({ member, amount, months }) => (
              <li key={member.id} className="row">
                <button
                  className="avatar-btn"
                  onClick={() => openMember(member.id)}
                  aria-label={`پرونده‌ی ${member.name}`}
                >
                  <Avatar name={member.name} id={member.id} />
                </button>
                <div className="row-main">
                  <strong>{member.name}</strong>
                  <span>
                    <AlertCircle size={12} style={{ verticalAlign: "-1px" }} /> {formatNumber(months.size)} ماه عقب
                    <span className="danger-text mobile-inline">، {formatCompact(amount)}</span>
                  </span>
                </div>
                <Money amount={amount} className="danger hide-sm" />
                <div className="row-end">
                  {member.phone && (
                    <a
                      className="icon-btn sm soft"
                      href={smsLink(member.phone, reminderText(fund, member.name, amount))}
                      aria-label={`پیامک یادآوری به ${member.name}`}
                      title="پیامک یادآوری"
                    >
                      <MessageSquareText size={17} />
                    </a>
                  )}
                  <button
                    className="icon-btn sm soft"
                    onClick={() => copyReminder(member, amount)}
                    aria-label="کپی متن یادآوری"
                    title="کپی متن یادآوری"
                  >
                    <Copy size={17} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {recent.length > 0 && (
        <section className="card flush">
          <div className="section-title">
            <h2>آخرین پرداخت‌ها</h2>
          </div>
          <ul className="rows">
            {recent.map((p) => (
              <li key={p.id} className="row">
                <Avatar name={memberName.get(p.memberId)} id={p.memberId} size="sm" />
                <div className="row-main">
                  <strong>{memberName.get(p.memberId) ?? "عضو سابق"}</strong>
                  <span>
                    {p.type === "contribution" ? "سهم" : "قسط"} {monthLabel(p.month)}، ثبت {formatDate(p.paidAt)}
                  </span>
                </div>
                <Money amount={p.amount} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
