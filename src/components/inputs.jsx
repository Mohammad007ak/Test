import { Minus, Plus } from "lucide-react";
import { MONTH_NAMES, makeMonthKey, parseMonthKey, toJalali, toPersianDigits } from "../lib/jalali.js";
import { formatCompact, parseAmount } from "../lib/format.js";

// Use as="div" around groups of buttons/selects, where a <label> would
// forward clicks on the caption to the first button.
export function Field({ label, hint, children, as: Tag = "label" }) {
  return (
    <Tag className="field">
      <span>{label}</span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </Tag>
  );
}

export function MoneyInput({ value, onChange, autoFocus }) {
  return (
    <div className="input big">
      <input
        type="text"
        inputMode="numeric"
        value={value ? value.toLocaleString("fa-IR") : ""}
        onChange={(e) => onChange(parseAmount(e.target.value))}
        placeholder="۰"
        autoFocus={autoFocus}
      />
      <span className="affix">تومان</span>
    </div>
  );
}

export function moneyHint(value) {
  return value >= 1000 ? `${formatCompact(value)} تومان` : undefined;
}

export function Stepper({ value, onChange, min = 1, max = 120, label }) {
  return (
    <div className="stepper" role="group" aria-label={label}>
      <button type="button" onClick={() => onChange(Math.min(max, value + 1))} aria-label="بیشتر">
        <Plus size={18} />
      </button>
      <output>{toPersianDigits(value)}</output>
      <button type="button" onClick={() => onChange(Math.max(min, value - 1))} aria-label="کمتر">
        <Minus size={18} />
      </button>
    </div>
  );
}

export function MonthPicker({ value, onChange }) {
  const { year, month } = parseMonthKey(value);
  const thisYear = toJalali().year;
  const years = [];
  for (let y = thisYear - 5; y <= thisYear + 1; y++) years.push(y);
  if (!years.includes(year)) years.unshift(year);

  return (
    <div className="select-row">
      <div className="input">
        <select value={month} onChange={(e) => onChange(makeMonthKey(year, Number(e.target.value)))} aria-label="ماه">
          {MONTH_NAMES.map((name, i) => (
            <option key={name} value={i + 1}>
              {name}
            </option>
          ))}
        </select>
      </div>
      <div className="input">
        <select value={year} onChange={(e) => onChange(makeMonthKey(Number(e.target.value), month))} aria-label="سال">
          {years.map((y) => (
            <option key={y} value={y}>
              {toPersianDigits(y)}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
