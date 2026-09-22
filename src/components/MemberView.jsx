import { useEffect, useState } from "react";
import { ArrowRight, Ban, CheckCircle2, Clock3, Copy, Eye, Hand, ShieldCheck, Trophy, Wallet } from "lucide-react";
import Pattern from "../ui/Pattern.jsx";
import { Logo } from "../ui/Logo.jsx";
import { Money, PageSkeleton, Ring } from "../ui/bits.jsx";
import { useToast } from "../ui/feedback.jsx";
import { api } from "../lib/api.js";
import { copyText, formatCard, formatCompact, formatNumber } from "../lib/format.js";
import { addMonths, formatDate, monthLabel } from "../lib/jalali.js";

const DRAW_STATUS = {
  confirmed: { label: "نهایی شد", badge: "brand", icon: Trophy },
  cancelled: { label: "لغو شد", badge: "danger", icon: Ban },
  pending: { label: "در انتظار", badge: "", icon: Clock3 },
};

export default function MemberView({ fundId, back }) {
  const [view, setView] = useState(null);
  const [error, setError] = useState(null);
  const toast = useToast();

  useEffect(() => {
    api("GET", `/api/funds/${fundId}/view`).then(setView, setError);
  }, [fundId]);

  const header = (
    <header className="appbar">
      <button className="icon-btn" onClick={() => back(view?.isManager)} aria-label="بازگشت">
        <ArrowRight size={20} />
      </button>
      <div className="appbar-title">
        <h1>{view?.fund.name ?? "صندوق"}</h1>
        <div className="sub">{view?.isManager ? "پیش‌نمایش صفحه‌ی اعضا" : view?.me ? `سلام ${view.me.name}` : ""}</div>
      </div>
      <span className="desktop-only">
        <Logo />
      </span>
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

  const { fund, me } = view;
  const dueNow = me?.dues.filter((d) => !d.paid && d.month <= view.currentMonth) ?? [];
  const dueTotal = dueNow.reduce((t, d) => t + d.amount, 0);
  const thisMonthDue = dueTotal - (me?.overdueAmount ?? 0);
  const copyCard = async () => {
    if (await copyText(fund.cardNumber)) toast("شماره کارت کپی شد");
  };

  return (
    <div className="home">
      {header}
      <div className="page">
        {view.isManager && (
          <div className="inline-note">
            <Eye size={16} />
            <span>اعضا این صفحه را می‌بینند؛ هر عضو فقط اطلاعات پرداخت خودش را.</span>
          </div>
        )}

        {me && (
          <section className={`hero ${me.overdueAmount ? "warn" : ""}`}>
            <Pattern />
            <div className="hero-label">
              {me.overdueAmount ? <Hand size={16} /> : <CheckCircle2 size={16} />}
              {me.overdueAmount ? "مانده‌ی پرداخت شما" : dueTotal ? "پرداخت این ماه" : "همه‌چیز پرداخت شده"}
            </div>
            <div className="hero-figure">
              {dueTotal ? (
                <>
                  {Math.round(dueTotal).toLocaleString("fa-IR")}
                  <small>تومان</small>
                </>
              ) : (
                "✓"
              )}
            </div>
            <p className="hero-sub">
              {me.overdueAmount
                ? `${formatCompact(me.overdueAmount)} عقب‌افتاده${thisMonthDue ? ` + ${formatCompact(thisMonthDue)} این ماه` : ""}`
                : `${formatNumber(me.shares)} سهم، ماهی ${formatCompact(me.shares * fund.contribution)} تومان`}
            </p>
          </section>
        )}

        {me && dueTotal > 0 && fund.cardNumber && (
          <section className="pay-card">
            <Pattern />
            <div className="pay-card-head">
              <span>واریز به کارت مدیر صندوق</span>
              <Wallet size={18} />
            </div>
            <div className="card-no">{formatCard(fund.cardNumber)}</div>
            <div className="card-foot">
              <span>{fund.cardHolder || fund.name}</span>
              <button className="btn sm" onClick={copyCard}>
                <Copy size={15} /> کپی شماره
              </button>
            </div>
          </section>
        )}

        {me?.loans.map((loan, i) => (
          <section className="card" key={i}>
            <div className="loan-top">
              <Ring value={loan.paidCount / loan.installments} size={58} done={loan.done} />
              <div>
                <strong>وام شما</strong>
                <span className="muted small">
                  <Money amount={loan.amount} />، قسط آخر {monthLabel(addMonths(loan.firstInstallmentMonth, loan.installments - 1))}
                </span>
              </div>
              {loan.done ? <span className="badge success">تسویه شد</span> : <span className="badge gold">فعال</span>}
            </div>
            <div className="loan-foot" style={{ marginTop: 14 }}>
              <span>
                {formatNumber(loan.paidCount)} از {formatNumber(loan.installments)} قسط پرداخت شده
              </span>
              <span>مانده {formatCompact(loan.remaining)} تومان</span>
            </div>
          </section>
        ))}

        {me && (
          <section className="card">
            <div className="section-title">
              <h2>پرداخت‌های شما</h2>
            </div>
            <ul className="ledger">
              {me.dues.slice(0, 12).map((due) => (
                <li key={due.month + due.type}>
                  <div>
                    {monthLabel(due.month)}
                    <span>{due.type === "contribution" ? "سهم ماهانه" : "قسط وام"}</span>
                  </div>
                  <Money amount={due.amount} />
                  {due.paid ? (
                    <span className="badge success">پرداخت شد</span>
                  ) : due.month < view.currentMonth ? (
                    <span className="badge danger">معوق</span>
                  ) : (
                    <span className="badge gold">این ماه</span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="card">
          <div className="section-title">
            <h2>صندوق در یک نگاه</h2>
          </div>
          <div className="kpis">
            <div className="kpi">
              <span>موجودی</span>
              <strong>{formatCompact(view.balance)}</strong>
              <small>تومان</small>
            </div>
            <div className="kpi">
              <span>اعضا</span>
              <strong>{formatNumber(view.memberCount)}</strong>
              <small>{formatNumber(view.totalShares)} سهم</small>
            </div>
            <div className="kpi">
              <span>هر وام</span>
              <strong>{formatCompact(fund.loanAmount)}</strong>
              <small>در {formatNumber(fund.installments)} قسط</small>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="section-title">
            <h2>دفتر قرعه‌کشی</h2>
            <span className="badge brand">
              <ShieldCheck size={13} /> غیرقابل ویرایش
            </span>
          </div>
          <p className="muted small" style={{ marginBottom: 16 }}>
            هر قرعه روی سرور انجام و ثبت می‌شود؛ مدیر نمی‌تواند آن را پاک یا عوض کند. قرعه‌های لغوشده هم اینجا می‌مانند.
          </p>
          {view.draws.length === 0 ? (
            <p className="muted small">هنوز قرعه‌کشی آنلاینی انجام نشده.</p>
          ) : (
            <ul className="timeline">
              {view.draws.map((draw, i) => {
                const s = DRAW_STATUS[draw.status];
                const Icon = s.icon;
                return (
                  <li key={i}>
                    <span className={`dot ${draw.status}`}>
                      <Icon size={15} />
                    </span>
                    <div className="t-body">
                      <div>
                        <strong className={draw.status === "cancelled" ? "struck" : ""}>{draw.winnerName}</strong>
                        <span>
                          {monthLabel(draw.month)}، {formatDate(new Date(draw.createdAt).toISOString())}
                        </span>
                      </div>
                      <span className={`badge ${s.badge}`}>{s.label}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {view.loans.length > 0 && (
          <section className="card">
            <div className="section-title">
              <h2>وام‌های داده‌شده</h2>
            </div>
            <ul className="ledger">
              {view.loans.map((loan, i) => (
                <li key={i}>
                  <div>
                    {loan.memberName}
                    <span>{monthLabel(loan.drawMonth)}</span>
                  </div>
                  <Money amount={loan.amount} />
                  {loan.viaDraw ? <span className="badge brand">با قرعه</span> : <span className="badge">ثبت دستی</span>}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
