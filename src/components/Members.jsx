import { useState } from "react";
import { MonthPicker, NumberInput } from "./inputs.jsx";
import { memberSummary, newId } from "../lib/fund.js";
import { formatMoney, formatNumber } from "../lib/format.js";
import { monthLabel } from "../lib/jalali.js";

function MemberForm({ initial, onSave, onCancel }) {
  const [draft, setDraft] = useState(initial);
  const set = (field) => (value) => setDraft((d) => ({ ...d, [field]: value }));

  return (
    <form
      className="form inline"
      onSubmit={(e) => {
        e.preventDefault();
        if (draft.name.trim()) onSave({ ...draft, name: draft.name.trim(), phone: draft.phone.trim() });
      }}
    >
      <label>
        نام
        <input value={draft.name} onChange={(e) => set("name")(e.target.value)} required autoFocus />
      </label>
      <label>
        موبایل
        <input
          value={draft.phone}
          onChange={(e) => set("phone")(e.target.value)}
          inputMode="tel"
          placeholder="۰۹۱۲..."
          dir="ltr"
        />
      </label>
      <label>
        تعداد سهم
        <NumberInput value={draft.shares} onChange={set("shares")} />
      </label>
      <label>
        ماه عضویت
        <MonthPicker value={draft.joinMonth} onChange={set("joinMonth")} />
      </label>
      <div className="row-actions">
        <button className="btn primary" type="submit">
          ذخیره
        </button>
        <button className="btn ghost" type="button" onClick={onCancel}>
          انصراف
        </button>
      </div>
    </form>
  );
}

export default function Members({ state, update, currentMonth }) {
  const [editing, setEditing] = useState(null);
  const { fund, members, payments, loans } = state;

  const saveMember = (member) => {
    update((s) => ({
      ...s,
      members: s.members.some((m) => m.id === member.id)
        ? s.members.map((m) => (m.id === member.id ? member : m))
        : [...s.members, member],
    }));
    setEditing(null);
  };

  const removeMember = (member) => {
    const hasHistory =
      payments.some((p) => p.memberId === member.id) || loans.some((l) => l.memberId === member.id);
    if (hasHistory) {
      alert("این عضو سابقه‌ی پرداخت یا وام دارد و قابل حذف نیست.");
      return;
    }
    if (confirm(`${member.name} حذف شود؟`)) {
      update((s) => ({ ...s, members: s.members.filter((m) => m.id !== member.id) }));
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="card-head">
          <h2>اعضا ({formatNumber(members.length)})</h2>
          {!editing && (
            <button
              className="btn primary"
              onClick={() =>
                setEditing({ id: newId(), name: "", phone: "", shares: 1, joinMonth: currentMonth < fund.startMonth ? fund.startMonth : currentMonth })
              }
            >
              + عضو جدید
            </button>
          )}
        </div>

        {editing && (
          <MemberForm initial={editing} onSave={saveMember} onCancel={() => setEditing(null)} />
        )}

        {members.length === 0 && !editing ? (
          <p className="empty">هنوز عضوی اضافه نشده. اولین عضو را اضافه کنید.</p>
        ) : (
          <ul className="list">
            {members.map((member) => {
              const summary = memberSummary(state, member.id, currentMonth);
              return (
                <li key={member.id}>
                  <div>
                    <strong>{member.name}</strong>
                    <span className="muted">
                      {formatNumber(member.shares)} سهم · از {monthLabel(member.joinMonth)}
                    </span>
                  </div>
                  <div className="member-meta">
                    <span>پرداختی: {formatMoney(summary.contributed)}</span>
                    {summary.activeLoan && <span className="tag">وام فعال</span>}
                    {summary.overdueCount > 0 && (
                      <span className="tag danger">معوق: {formatMoney(summary.overdueAmount)}</span>
                    )}
                  </div>
                  <div className="row-actions">
                    <button className="btn small ghost" onClick={() => setEditing(member)}>
                      ویرایش
                    </button>
                    <button className="btn small ghost" onClick={() => removeMember(member)}>
                      حذف
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
