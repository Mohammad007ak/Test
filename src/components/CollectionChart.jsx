import { useState } from "react";
import { duesForMonth, sum } from "../lib/fund.js";
import { addMonths, MONTH_NAMES, monthLabel, parseMonthKey } from "../lib/jalali.js";
import { formatMoney, formatNumber } from "../lib/format.js";

// One series: the share of each month's dues that was collected. The
// current month is in the accent so "this month so far" reads as partial.
export default function CollectionChart({ state, currentMonth, months = 6 }) {
  const [active, setActive] = useState(null);
  const start = state.fund.startMonth;
  const data = [];
  for (let i = months - 1; i >= 0; i--) {
    const month = addMonths(currentMonth, -i);
    if (month < start) continue;
    const dues = duesForMonth(state, month);
    const expected = sum(dues);
    const collected = sum(dues.filter((d) => d.paid));
    data.push({ month, expected, collected, rate: expected ? collected / expected : 0 });
  }
  if (data.length === 0) return null;

  return (
    <div>
      <div className="chart" style={{ "--cols": data.length }} role="list" aria-label="درصد وصول ماهانه">
        <span className="y-tick" style={{ bottom: "100%" }} aria-hidden="true">
          ۱۰۰٪
        </span>
        <span className="y-tick" style={{ bottom: "50%" }} aria-hidden="true">
          ۵۰٪
        </span>
        {data.map((d) => {
          const h = `${Math.max(2, d.rate * 100)}%`;
          const isCurrent = d.month === currentMonth;
          return (
            <div
              key={d.month}
              role="listitem"
              tabIndex={0}
              className={`chart-col ${isCurrent ? "current" : ""}`}
              style={{ "--h": h }}
              onMouseEnter={() => setActive(d.month)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(d.month)}
              onBlur={() => setActive(null)}
              aria-label={`${monthLabel(d.month)}: ${formatNumber(Math.round(d.rate * 100))} درصد`}
            >
              {(isCurrent || active === d.month) && active !== d.month && (
                <span className="cap">{formatNumber(Math.round(d.rate * 100))}٪</span>
              )}
              <div className="bar-mark" style={{ height: h }} />
              {active === d.month && (
                <div className="tooltip">
                  <b>{monthLabel(d.month)}</b>
                  <br />
                  وصول {formatMoney(d.collected)} از {formatMoney(d.expected)}
                  <br />
                  {formatNumber(Math.round(d.rate * 100))}٪{isCurrent ? " (ماه جاری)" : ""}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="chart-x" style={{ "--cols": data.length }} aria-hidden="true">
        {data.map((d) => (
          <span key={d.month}>{MONTH_NAMES[parseMonthKey(d.month).month - 1]}</span>
        ))}
      </div>
    </div>
  );
}
