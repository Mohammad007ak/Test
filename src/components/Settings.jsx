import { useRef, useState } from "react";
import { CreditCard, Download, Info, Trash2, Upload } from "lucide-react";
import { useDialog, useToast } from "../ui/feedback.jsx";
import { Field, MoneyInput, MonthPicker, Stepper, moneyHint } from "./inputs.jsx";
import { api } from "../lib/api.js";
import { isValidState } from "../lib/fund.js";
import { formatCard } from "../lib/format.js";

const EDITABLE = ["name", "contribution", "loanAmount", "installments", "startMonth", "cardNumber", "cardHolder"];
const editable = (fund) => Object.fromEntries(EDITABLE.map((k) => [k, fund[k] ?? ""]));

export default function Settings({ state, update, server, goHome }) {
  const [draft, setDraft] = useState(() => editable(state.fund));
  const fileInput = useRef(null);
  const toast = useToast();
  const confirm = useDialog();
  const set = (field) => (value) => setDraft((d) => ({ ...d, [field]: value }));

  const cardDigits = (draft.cardNumber ?? "").replace(/\D/g, "");
  const cardValid = cardDigits.length === 0 || cardDigits.length === 16;
  const dirty = JSON.stringify(draft) !== JSON.stringify(editable(state.fund));
  const valid = draft.name.trim() && draft.contribution > 0 && draft.loanAmount > 0 && cardValid;

  const save = () => {
    // Merge only the edited fields so a concurrent change (e.g. a new
    // lottery cycle) isn't overwritten by this form's older copy.
    update((s) => ({ ...s, fund: { ...s.fund, ...draft, name: draft.name.trim(), cardNumber: cardDigits } }));
    setDraft((d) => ({ ...d, name: d.name.trim() }));
    toast("تنظیمات ذخیره شد");
  };

  const exportData = () => {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `sandoghche-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    toast("فایل پشتیبان دانلود شد");
  };

  const importData = async (file) => {
    let data;
    try {
      data = JSON.parse(await file.text());
      if (!isValidState(data)) throw new Error();
    } catch {
      toast("این فایل پشتیبان معتبر نیست", { tone: "error" });
      return;
    }
    const ok = await confirm({
      title: "بازیابی از فایل پشتیبان",
      body: `اطلاعات فعلی صندوق با «${data.fund.name}» از فایل پشتیبان جایگزین می‌شود.`,
      confirmLabel: "جایگزین کن",
      tone: "danger",
    });
    if (!ok) return;
    update(() => data);
    setDraft(editable(data.fund));
    toast("اطلاعات بازیابی شد");
  };

  const deleteFund = async () => {
    const ok = await confirm({
      title: "حذف همیشگی صندوق",
      body: "همه‌ی اعضا، پرداخت‌ها، وام‌ها و سابقه‌ی قرعه‌ها پاک می‌شود و برگشت‌پذیر نیست. برای تأیید، اسم صندوق را بنویسید.",
      requireText: state.fund.name,
      confirmLabel: "حذف همیشگی",
      tone: "danger",
    });
    if (!ok) return;
    try {
      await api("DELETE", `/api/funds/${server.fundId}`);
      toast("صندوق حذف شد");
      goHome();
    } catch (e) {
      toast(e.message, { tone: "error" });
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>تنظیمات</h1>
          <p>مشخصات صندوق، کارت واریز و پشتیبان‌گیری.</p>
        </div>
      </div>

      <section className="card">
        <div className="section-title">
          <h2>مشخصات صندوق</h2>
        </div>
        <div className="form-grid">
          <Field label="اسم صندوق">
            <div className="input">
              <input value={draft.name} onChange={(e) => set("name")(e.target.value)} />
            </div>
          </Field>
          <div className="form-grid two">
            <Field label="سهم ماهانه" hint={moneyHint(draft.contribution)}>
              <MoneyInput value={draft.contribution} onChange={set("contribution")} />
            </Field>
            <Field label="مبلغ هر وام" hint={moneyHint(draft.loanAmount)}>
              <MoneyInput value={draft.loanAmount} onChange={set("loanAmount")} />
            </Field>
            <Field label="تعداد اقساط" as="div">
              <Stepper value={draft.installments} onChange={set("installments")} label="تعداد اقساط" />
            </Field>
            <Field label="ماه شروع" as="div">
              <MonthPicker value={draft.startMonth} onChange={set("startMonth")} />
            </Field>
          </div>
          <div className="inline-note">
            <Info size={16} />
            <span>تغییر مبلغ وام یا تعداد اقساط روی وام‌هایی که قبلاً داده شده اثری ندارد.</span>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="section-title">
          <h2>کارت واریز</h2>
        </div>
        <p className="muted small" style={{ marginBottom: 14 }}>
          اعضا این کارت را در صفحه‌ی خودشان و در پیامک یادآوری می‌بینند و می‌توانند شماره را کپی کنند.
        </p>
        <div className="form-grid two">
          <Field label="شماره کارت" hint={cardValid ? undefined : "شماره کارت باید ۱۶ رقم باشد."}>
            <div className="input">
              <CreditCard size={17} className="muted" />
              <input
                value={formatCard(draft.cardNumber ?? "")}
                onChange={(e) => set("cardNumber")(e.target.value.replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/\D/g, "").slice(0, 16))}
                inputMode="numeric"
                placeholder="۶۰۳۷ ۹۹۷۱ ۰۰۰۰ ۰۰۰۰"
                dir="ltr"
              />
            </div>
          </Field>
          <Field label="به نام">
            <div className="input">
              <input value={draft.cardHolder ?? ""} onChange={(e) => set("cardHolder")(e.target.value)} placeholder="نام صاحب کارت" />
            </div>
          </Field>
        </div>
      </section>

      {dirty && (
        <div className="split card save-bar">
          <span className="small">تغییرات ذخیره نشده دارید.</span>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn ghost sm" onClick={() => setDraft(editable(state.fund))}>
              بازگرداندن
            </button>
            <button className="btn primary sm" onClick={save} disabled={!valid}>
              ذخیره
            </button>
          </div>
        </div>
      )}

      <section className="card">
        <div className="section-title">
          <h2>پشتیبان‌گیری</h2>
        </div>
        <p className="muted small" style={{ marginBottom: 14 }}>
          اطلاعات روی سرور ذخیره می‌شود. برای خیال راحت، هر چند وقت یک فایل پشتیبان هم نگه دارید.
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button className="btn outline" onClick={exportData}>
            <Download size={18} /> دانلود فایل پشتیبان
          </button>
          <button className="btn outline" onClick={() => fileInput.current.click()}>
            <Upload size={18} /> بازیابی از فایل
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="application/json"
            hidden
            onChange={(e) => {
              if (e.target.files[0]) importData(e.target.files[0]);
              e.target.value = "";
            }}
          />
        </div>
      </section>

      <section className="card danger-zone">
        <div className="section-title">
          <h2>حذف صندوق</h2>
        </div>
        <p className="muted small" style={{ marginBottom: 14 }}>
          صندوق و همه‌ی سابقه‌اش برای شما و همه‌ی اعضا پاک می‌شود.
        </p>
        <button className="btn danger" onClick={deleteFund}>
          <Trash2 size={18} /> حذف همیشگی صندوق
        </button>
      </section>
    </div>
  );
}
