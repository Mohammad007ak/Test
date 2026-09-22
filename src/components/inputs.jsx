import { MONTH_NAMES, makeMonthKey, parseMonthKey, toJalali, toPersianDigits } from "../lib/jalali.js";
import { parseAmount } from "../lib/format.js";

export function MoneyInput({ value, onChange, ...props }) {
  return (
    <div className="money-input">
      <input
        type="text"
        inputMode="numeric"
        value={value ? value.toLocaleString("fa-IR") : ""}
        onChange={(e) => onChange(parseAmount(e.target.value))}
        {...props}
      />
      <span>تومان</span>
    </div>
  );
}

export function NumberInput({ value, onChange, min = 1, ...props }) {
  return (
    <input
      type="text"
      inputMode="numeric"
      value={value ? toPersianDigits(value) : ""}
      onChange={(e) => onChange(Math.max(min, parseAmount(e.target.value)))}
      {...props}
    />
  );
}

export function MonthPicker({ value, onChange }) {
  const { year, month } = parseMonthKey(value);
  const thisYear = toJalali().year;
  const years = [];
  for (let y = thisYear - 5; y <= thisYear + 1; y++) years.push(y);
  if (!years.includes(year)) years.unshift(year);

  return (
    <div className="month-picker">
      <select value={month} onChange={(e) => onChange(makeMonthKey(year, Number(e.target.value)))}>
        {MONTH_NAMES.map((name, i) => (
          <option key={name} value={i + 1}>
            {name}
          </option>
        ))}
      </select>
      <select value={year} onChange={(e) => onChange(makeMonthKey(Number(e.target.value), month))}>
        {years.map((y) => (
          <option key={y} value={y}>
            {toPersianDigits(y)}
          </option>
        ))}
      </select>
    </div>
  );
}
