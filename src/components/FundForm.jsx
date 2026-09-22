import { useState } from "react";
import { MoneyInput, MonthPicker, NumberInput } from "./inputs.jsx";
import { currentMonthKey } from "../lib/jalali.js";
import { formatMoney } from "../lib/format.js";

const DEFAULTS = {
  name: "",
  contribution: 1_000_000,
  loanAmount: 20_000_000,
  installments: 10,
  startMonth: currentMonthKey(),
  cycle: 1,
};

export default function FundForm({ fund, onSave, submitLabel }) {
  const [draft, setDraft] = useState(fund ?? DEFAULTS);
  const set = (field) => (value) => setDraft((d) => ({ ...d, [field]: value }));
  const valid = draft.name.trim() && draft.contribution > 0 && draft.loanAmount > 0 && draft.installments > 0;

  return (
    <form
      className="form"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onSave({ ...draft, name: draft.name.trim() });
      }}
    >
      <label>
        اسم صندوق
        <input
          value={draft.name}
          onChange={(e) => set("name")(e.target.value)}
          placeholder="مثلاً صندوق خانوادگی مهر"
          required
        />
      </label>
      <label>
        سهم ماهانه (برای هر سهم)
        <MoneyInput value={draft.contribution} onChange={set("contribution")} />
      </label>
      <label>
        مبلغ هر وام
        <MoneyInput value={draft.loanAmount} onChange={set("loanAmount")} />
      </label>
      <label>
        تعداد اقساط وام
        <NumberInput value={draft.installments} onChange={set("installments")} />
        <small>
          هر قسط حدوداً {formatMoney(Math.floor(draft.loanAmount / Math.max(1, draft.installments)))}
        </small>
      </label>
      <label>
        ماه شروع صندوق
        <MonthPicker value={draft.startMonth} onChange={set("startMonth")} />
      </label>
      <button className="btn primary" type="submit" disabled={!valid}>
        {submitLabel}
      </button>
    </form>
  );
}
