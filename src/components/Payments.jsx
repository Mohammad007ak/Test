import { useState } from "react";
import { Check, CheckCheck, ChevronLeft, ChevronRight, Search, SearchX } from "lucide-react";
import { Avatar, EmptyState, Money, Segmented } from "../ui/bits.jsx";
import { useDialog, useToast } from "../ui/feedback.jsx";
import { duesForMonth, matchesDue, paymentForDue, sum } from "../lib/fund.js";
import { formatCompact, formatNumber } from "../lib/format.js";
import { addMonths, monthLabel } from "../lib/jalali.js";

export default function Payments({ state, update, currentMonth, openMember }) {
  const [month, setMonth] = useState(currentMonth);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const toast = useToast();
  const confirm = useDialog();

  const dues = duesForMonth(state, month);
  const collected = sum(dues.filter((d) => d.paid));
  const expected = sum(dues);
  const isPast = month < currentMonth;
  const canGoForward = month < currentMonth;
  const canGoBack = month > state.fund.startMonth;

  const setPaid = (due, paid) =>
    update((s) => ({
      ...s,
      payments: paid ? [...s.payments, paymentForDue(due)] : s.payments.filter((p) => !matchesDue(p, due)),
    }));

  const toggle = (due, member) => {
    setPaid(due, !due.paid);
    toast(due.paid ? `پرداخت ${member.name} برداشته شد` : `پرداخت ${member.name} ثبت شد`, {
      action: { label: "برگرداندن", onClick: () => setPaid(due, due.paid) },
    });
  };

  const markAllPaid = async () => {
    const unpaid = dues.filter((d) => !d.paid);
    const ok = await confirm({
      title: "ثبت همه‌ی پرداخت‌ها",
      body: `${formatNumber(unpaid.length)} پرداخت به مبلغ ${formatCompact(sum(unpaid))} تومان برای ${monthLabel(month)} ثبت شود؟`,
      confirmLabel: "ثبت همه",
    });
    if (!ok) return;
    update((s) => ({ ...s, payments: [...s.payments, ...unpaid.map(paymentForDue)] }));
    toast(`${formatNumber(unpaid.length)} پرداخت ثبت شد`);
  };

  const rows = state.members
    .map((member) => ({ member, dues: dues.filter((d) => d.memberId === member.id) }))
    .filter((row) => row.dues.length > 0);

  const counts = {
    all: rows.length,
    open: rows.filter((r) => r.dues.some((d) => !d.paid)).length,
    done: rows.filter((r) => r.dues.every((d) => d.paid)).length,
  };

  const visible = rows.filter(({ member, dues: memberDues }) => {
    if (query && !member.name.includes(query.trim())) return false;
    if (filter === "open") return memberDues.some((d) => !d.paid);
    if (filter === "done") return memberDues.every((d) => d.paid);
    return true;
  });

  return (
    <div className="page">
      <section className="card">
        <div className="month-nav">
          <button
            className="icon-btn soft"
            onClick={() => setMonth(addMonths(month, -1))}
            disabled={!canGoBack}
            aria-label="ماه قبل"
          >
            <ChevronRight size={20} />
          </button>
          <div>
            <strong>{monthLabel(month)}</strong>
            <span className="muted small">
              {month === currentMonth ? "ماه جاری" : isPast ? "ماه گذشته" : ""}
            </span>
          </div>
          <button
            className="icon-btn soft"
            onClick={() => setMonth(addMonths(month, 1))}
            disabled={!canGoForward}
            aria-label="ماه بعد"
          >
            <ChevronLeft size={20} />
          </button>
        </div>
        <div className="bar" style={{ margin: "16px 0 8px" }}>
          <div style={{ width: `${expected ? (collected / expected) * 100 : 0}%` }} />
        </div>
        <div className="split small">
          <span>
            وصول‌شده <Money amount={collected} />
          </span>
          <span className="muted">از {formatCompact(expected)} تومان</span>
        </div>
      </section>

      <div className="toolbar">
        <Segmented
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: "همه", count: counts.all },
            { value: "open", label: "مانده", count: counts.open },
            { value: "done", label: "تسویه", count: counts.done },
          ]}
        />
        <label className="input search">
          <Search size={17} className="muted" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جست‌وجوی عضو" />
        </label>
      </div>

      <section className="card flush">
        {rows.length === 0 ? (
          <EmptyState title="پرداختی برای این ماه نیست" text="اعضایی که از این ماه عضو شده‌اند اینجا دیده می‌شوند." />
        ) : visible.length === 0 ? (
          <EmptyState icon={SearchX} title="چیزی پیدا نشد" text="فیلتر یا جست‌وجو را تغییر دهید." />
        ) : (
          <ul className="rows">
            {visible.map(({ member, dues: memberDues }) => (
              <li key={member.id} className="row pay-row">
                <button className="avatar-btn" onClick={() => openMember(member.id)} aria-label={`پرونده‌ی ${member.name}`}>
                  <Avatar name={member.name} id={member.id} />
                </button>
                <div className="row-main">
                  <strong>{member.name}</strong>
                  <span>
                    {memberDues.every((d) => d.paid)
                      ? "تسویه"
                      : `${formatCompact(sum(memberDues.filter((d) => !d.paid)))} تومان مانده`}
                  </span>
                </div>
                <div className="row-end">
                  {memberDues.map((due) => (
                    <button
                      key={due.type + (due.loanId ?? "")}
                      className={`pay-toggle ${due.paid ? "paid" : ""} ${isPast ? "late" : ""}`}
                      onClick={() => toggle(due, member)}
                      aria-pressed={due.paid}
                    >
                      <span className="tick">
                        <Check size={15} strokeWidth={3} />
                      </span>
                      <span className="pay-meta">
                        <small>{due.type === "contribution" ? "سهم ماهانه" : "قسط وام"}</small>
                        {formatCompact(due.amount)}
                      </span>
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {dues.some((d) => !d.paid) && (
        <button className="btn outline block" onClick={markAllPaid}>
          <CheckCheck size={18} /> همه‌ی پرداخت‌های {monthLabel(month)} انجام شد
        </button>
      )}
    </div>
  );
}
