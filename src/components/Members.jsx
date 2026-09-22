import { useEffect, useState } from "react";
import { ChevronLeft, MessageSquareText, Pencil, Phone, Search, Trash2, UserPlus, Users } from "lucide-react";
import Sheet from "../ui/Sheet.jsx";
import { Avatar, EmptyState, Money } from "../ui/bits.jsx";
import { useDialog, useToast } from "../ui/feedback.jsx";
import { Field, MonthPicker, Stepper } from "./inputs.jsx";
import { listDues, loanProgress, memberSummary, newId } from "../lib/fund.js";
import { formatCompact, formatNumber, reminderText, smsLink } from "../lib/format.js";
import { normalizePhone } from "../lib/phone.js";
import { monthLabel, toPersianDigits } from "../lib/jalali.js";

export function MemberForm({ open, initial, onSave, onClose }) {
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState(null);
  const [isNew, setIsNew] = useState(true);
  useEffect(() => {
    if (open) {
      setDraft(initial);
      setError(null);
      setIsNew(!initial?.name);
    }
  }, [open, initial]);
  const set = (field) => (value) => setDraft((d) => ({ ...d, [field]: value }));

  const submit = () => {
    if (!draft.name.trim()) return setError("نام عضو را وارد کنید.");
    const phone = draft.phone.trim() ? normalizePhone(draft.phone) : "";
    if (phone === null) return setError("شماره موبایل درست نیست؛ مثل ۰۹۱۲ ۱۲۳ ۴۵۶۷");
    onSave({ ...draft, name: draft.name.trim(), phone });
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={isNew ? "عضو جدید" : "ویرایش عضو"}
      footer={
        <>
          <button className="btn outline" onClick={onClose}>
            انصراف
          </button>
          <button className="btn primary" onClick={submit}>
            {isNew ? "افزودن عضو" : "ذخیره"}
          </button>
        </>
      }
    >
      {draft && (
        <form
          className="form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <Field label="نام و نام خانوادگی">
            <div className="input">
              <input value={draft.name} onChange={(e) => set("name")(e.target.value)} autoFocus />
            </div>
          </Field>
          <Field label="موبایل" hint="با همین شماره وارد می‌شود و وضعیت خودش را می‌بیند.">
            <div className="input">
              <Phone size={17} className="muted" />
              <input
                value={draft.phone}
                onChange={(e) => set("phone")(e.target.value)}
                inputMode="tel"
                placeholder="۰۹۱۲ ۱۲۳ ۴۵۶۷"
                dir="ltr"
              />
            </div>
          </Field>
          <div className="form-grid two">
            <Field label="تعداد سهم" as="div">
              <Stepper value={draft.shares} onChange={set("shares")} max={20} label="تعداد سهم" />
            </Field>
            <Field label="عضو از" as="div">
              <MonthPicker value={draft.joinMonth} onChange={set("joinMonth")} />
            </Field>
          </div>
          {error && <p className="error-text">{error}</p>}
          <button type="submit" hidden />
        </form>
      )}
    </Sheet>
  );
}

export function MemberSheet({ state, memberId, currentMonth, onClose, onEdit, onDelete }) {
  const member = state.members.find((m) => m.id === memberId);
  const summary = member && memberSummary(state, member.id, currentMonth);
  const dues = member
    ? listDues(state, currentMonth)
        .filter((d) => d.memberId === member.id)
        .sort((a, b) => b.month.localeCompare(a.month))
        .slice(0, 8)
    : [];
  const loans = member ? state.loans.filter((l) => l.memberId === member.id) : [];

  return (
    <Sheet open={Boolean(member)} onClose={onClose} title="پرونده‌ی عضو">
      {member && (
        <>
          <div className="profile">
            <Avatar name={member.name} id={member.id} size="lg" />
            <div>
              <strong>{member.name}</strong>
              <span className="muted small">
                {formatNumber(member.shares)} سهم، عضو از {monthLabel(member.joinMonth)}
              </span>
            </div>
          </div>

          <div className="row-actions" style={{ display: "flex", gap: 8, marginBottom: 18 }}>
            {member.phone && (
              <>
                <a className="btn sm outline" href={`tel:${member.phone}`}>
                  <Phone size={16} /> تماس
                </a>
                <a
                  className="btn sm outline"
                  href={smsLink(member.phone, reminderText(state.fund, member.name, summary.overdueAmount))}
                >
                  <MessageSquareText size={16} /> پیامک
                </a>
              </>
            )}
            <button className="btn sm outline" onClick={() => onEdit(member)}>
              <Pencil size={16} /> ویرایش
            </button>
            <button className="btn sm danger" onClick={() => onDelete(member)}>
              <Trash2 size={16} /> حذف
            </button>
          </div>

          <div className="mini-stats">
            <div>
              <span>کل پرداختی</span>
              <strong>{formatCompact(summary.contributed)}</strong>
            </div>
            <div>
              <span>معوق</span>
              <strong className={summary.overdueAmount ? "danger" : ""}>
                {summary.overdueAmount ? formatCompact(summary.overdueAmount) : "ندارد"}
              </strong>
            </div>
            <div>
              <span>وام</span>
              <strong>{summary.activeLoan ? "فعال" : loans.length ? "تسویه" : "ندارد"}</strong>
            </div>
          </div>

          {loans.map((loan) => {
            const p = loanProgress(state, loan);
            return (
              <div key={loan.id} className="preview-card" style={{ marginBottom: 18 }}>
                <div>
                  <span>وام {monthLabel(loan.drawMonth)}</span>
                  <Money amount={loan.amount} />
                </div>
                <div className="bar">
                  <div style={{ width: `${(p.paidCount / loan.installments) * 100}%` }} />
                </div>
                <div>
                  <span>
                    {formatNumber(p.paidCount)} از {formatNumber(loan.installments)} قسط
                  </span>
                  <span>مانده {formatCompact(p.remaining)}</span>
                </div>
              </div>
            );
          })}

          <h3 style={{ marginBottom: 6 }}>پرداخت‌های اخیر</h3>
          {member.phone ? null : (
            <p className="muted small" style={{ marginBottom: 6 }}>
              شماره‌ی موبایل ثبت نشده؛ این عضو نمی‌تواند وارد شود.
            </p>
          )}
          <ul className="ledger">
            {dues.map((d) => (
              <li key={d.month + d.type + (d.loanId ?? "")}>
                <div>
                  {monthLabel(d.month)}
                  <span>{d.type === "contribution" ? "سهم ماهانه" : "قسط وام"}</span>
                </div>
                <Money amount={d.amount} />
                {d.paid ? (
                  <span className="badge success">پرداخت شد</span>
                ) : d.month < currentMonth ? (
                  <span className="badge danger">معوق</span>
                ) : (
                  <span className="badge">این ماه</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </Sheet>
  );
}

export function blankMember(fund, currentMonth) {
  return {
    id: newId(),
    name: "",
    phone: "",
    shares: 1,
    joinMonth: currentMonth < fund.startMonth ? fund.startMonth : currentMonth,
  };
}

export default function Members({ state, currentMonth, openMember, editMember }) {
  const [query, setQuery] = useState("");
  const { fund, members } = state;
  const add = () => editMember(blankMember(fund, currentMonth));
  const visible = members.filter((m) => !query || m.name.includes(query.trim()));

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>اعضا</h1>
          <p>
            {formatNumber(members.length)} عضو، {formatNumber(members.reduce((t, m) => t + m.shares, 0))} سهم
          </p>
        </div>
        <button className="btn primary" onClick={add}>
          <UserPlus size={18} /> عضو جدید
        </button>
      </div>

      {members.length > 5 && (
        <label className="input search">
          <Search size={17} className="muted" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جست‌وجوی عضو" />
        </label>
      )}

      <section className="card flush">
        {members.length === 0 ? (
          <EmptyState
            icon={Users}
            title="هنوز عضوی ندارید"
            text="اعضا را با شماره موبایل اضافه کنید تا هر کدام وضعیت خودش را ببیند."
            action={
              <button className="btn primary" onClick={add}>
                <UserPlus size={18} /> افزودن اولین عضو
              </button>
            }
          />
        ) : (
          <ul className="rows">
            {visible.map((member) => {
              const summary = memberSummary(state, member.id, currentMonth);
              return (
                <li key={member.id}>
                  <button className="row" onClick={() => openMember(member.id)}>
                    <Avatar name={member.name} id={member.id} />
                    <div className="row-main">
                      <strong>{member.name}</strong>
                      <span>
                        {formatNumber(member.shares)} سهم
                        {member.phone ? `، ${toPersianDigits(member.phone)}` : "، بدون موبایل"}
                      </span>
                    </div>
                    <div className="row-end">
                      {summary.activeLoan && <span className="badge gold">وام فعال</span>}
                      {summary.overdueCount > 0 ? (
                        <span className="badge danger">{formatCompact(summary.overdueAmount)} معوق</span>
                      ) : (
                        <span className="badge success">به‌روز</span>
                      )}
                      <ChevronLeft size={18} className="muted" />
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

export function useMemberActions({ state, update }) {
  const toast = useToast();
  const confirm = useDialog();

  const remove = async (member) => {
    const hasHistory =
      state.payments.some((p) => p.memberId === member.id) || state.loans.some((l) => l.memberId === member.id);
    if (hasHistory) {
      await confirm({
        title: "این عضو قابل حذف نیست",
        body: `${member.name} سابقه‌ی پرداخت یا وام دارد. برای حفظ شفافیت حساب‌ها، اعضای دارای سابقه حذف نمی‌شوند.`,
        confirmLabel: "متوجه شدم",
        cancelLabel: "بستن",
        tone: "gold",
      });
      return false;
    }
    const ok = await confirm({
      title: `حذف ${member.name}؟`,
      body: "این عضو از صندوق حذف می‌شود.",
      confirmLabel: "حذف",
      tone: "danger",
    });
    if (!ok) return false;
    update((s) => ({ ...s, members: s.members.filter((m) => m.id !== member.id) }));
    toast(`${member.name} حذف شد`);
    return true;
  };

  const save = (member) => {
    const exists = state.members.some((m) => m.id === member.id);
    update((s) => ({
      ...s,
      members: exists ? s.members.map((m) => (m.id === member.id ? member : m)) : [...s.members, member],
    }));
    toast(exists ? "تغییرات ذخیره شد" : `${member.name} به صندوق اضافه شد`);
  };

  return { save, remove };
}
