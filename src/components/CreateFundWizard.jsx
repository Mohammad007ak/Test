import { useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import Sheet from "../ui/Sheet.jsx";
import { Money, Spinner } from "../ui/bits.jsx";
import { Field, MoneyInput, MonthPicker, Stepper, moneyHint } from "./inputs.jsx";
import { createEmptyState } from "../lib/fund.js";
import { currentMonthKey } from "../lib/jalali.js";
import { formatNumber } from "../lib/format.js";

const STEPS = [
  { title: "اسم صندوق", text: "اسمی که اعضا صندوق را با آن می‌شناسند." },
  { title: "سهم و وام", text: "هر عضو ماهانه چقدر می‌گذارد و هر بار چقدر وام داده می‌شود؟" },
  { title: "اقساط و شروع", text: "وام در چند قسط برمی‌گردد و صندوق از چه ماهی شروع شده؟" },
];

export default function CreateFundWizard({ open, onClose, onCreate }) {
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [fund, setFund] = useState({
    name: "",
    contribution: 1_000_000,
    loanAmount: 20_000_000,
    installments: 10,
    startMonth: currentMonthKey(),
    cycle: 1,
  });
  const set = (field) => (value) => setFund((f) => ({ ...f, [field]: value }));

  const valid = [fund.name.trim().length > 1, fund.contribution > 0 && fund.loanAmount > 0, fund.installments > 0];
  const last = step === STEPS.length - 1;

  const next = async () => {
    if (!valid[step]) return;
    if (!last) return setStep(step + 1);
    setBusy(true);
    const ok = await onCreate({ ...createEmptyState(), fund: { ...fund, name: fund.name.trim() } });
    setBusy(false);
    if (ok) {
      setStep(0);
      setFund((f) => ({ ...f, name: "" }));
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="صندوق جدید"
      footer={
        <>
          {step > 0 && (
            <button className="btn outline" onClick={() => setStep(step - 1)}>
              <ArrowRight size={18} /> قبلی
            </button>
          )}
          <button className="btn primary" onClick={next} disabled={!valid[step] || busy}>
            {busy ? <Spinner /> : last ? "ساخت صندوق" : "ادامه"}
            {!last && !busy && <ArrowLeft size={18} />}
          </button>
        </>
      }
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          next();
        }}
      >
        <div className="wizard-steps" aria-hidden="true">
          {STEPS.map((_, i) => (
            <i key={i} className={i <= step ? "done" : ""} />
          ))}
        </div>
        <div className="wizard-intro">
          <h3>{STEPS[step].title}</h3>
          <p>{STEPS[step].text}</p>
        </div>

        {step === 0 && (
          <Field label="اسم صندوق">
            <div className="input big">
              <input
                value={fund.name}
                onChange={(e) => set("name")(e.target.value)}
                placeholder="مثلاً صندوق خانوادگی مهر"
                autoFocus
              />
            </div>
          </Field>
        )}

        {step === 1 && (
          <div className="form-grid">
            <Field label="سهم ماهانه‌ی هر عضو" hint={moneyHint(fund.contribution)}>
              <MoneyInput value={fund.contribution} onChange={set("contribution")} autoFocus />
            </Field>
            <Field label="مبلغ هر وام" hint={moneyHint(fund.loanAmount)}>
              <MoneyInput value={fund.loanAmount} onChange={set("loanAmount")} />
            </Field>
          </div>
        )}

        {step === 2 && (
          <div className="form-grid">
            <Field label="تعداد اقساط" as="div">
              <Stepper value={fund.installments} onChange={set("installments")} label="تعداد اقساط" />
            </Field>
            <Field label="ماه شروع صندوق" as="div">
              <MonthPicker value={fund.startMonth} onChange={set("startMonth")} />
            </Field>
            <div className="preview-card">
              <div>
                <span>هر قسط وام</span>
                <Money amount={Math.floor(fund.loanAmount / fund.installments)} />
              </div>
              <div>
                <span>هر وام برابر است با</span>
                <strong>{formatNumber(Math.ceil(fund.loanAmount / fund.contribution))} سهم ماهانه</strong>
              </div>
            </div>
          </div>
        )}
        <button type="submit" hidden />
      </form>
    </Sheet>
  );
}
