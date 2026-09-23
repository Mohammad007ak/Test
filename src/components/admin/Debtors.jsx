import { useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { EmptyState, PageSkeleton } from "../../ui/bits.jsx";
import { api } from "../../lib/api.js";
import { formatCompact, formatNumber } from "../../lib/format.js";
import { toPersianDigits } from "../../lib/jalali.js";
import { formatWhen, planTitle, toman } from "./shared.jsx";

// Members whose installments Digipay's guarantee paid and who haven't
// settled yet: they sit out draws until they do.
export default function Debtors({ open }) {
  const [debtors, setDebtors] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    api("GET", "/api/ops/debtors").then((r) => setDebtors(r.debtors), setError);
  }, []);

  if (error) return <p className="error-text">{error.message}</p>;
  if (!debtors) return <PageSkeleton />;
  if (debtors.length === 0) {
    return (
      <section className="card">
        <EmptyState icon={CheckCircle2} title="بدهی بازی نیست" text="همه‌ی اقساط ضمانت‌شده تسویه شده‌اند." />
      </section>
    );
  }

  const total = debtors.reduce((t, d) => t + d.amount, 0);
  return (
    <div className="stack">
      <div className="inline-note">
        <span>
          {formatNumber(debtors.length)} بدهکار، جمعاً <b>{toman(total)}</b>. بدهکار تا تسویه در قرعه شرکت داده نمی‌شود
          و می‌تواند از صفحه‌ی دوره‌اش بدهی را پرداخت کند.
        </span>
      </div>
      <section className="card flush">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>عضو</th>
                <th>طرح</th>
                <th>ماه‌های معوق</th>
                <th>مبلغ</th>
                <th>بدهکار از</th>
              </tr>
            </thead>
            <tbody>
              {debtors.map((d) => (
                <tr
                  key={d.circleId + d.position}
                  className="clickable"
                  onClick={() => open("ops", "circles", d.circleId)}
                >
                  <td>
                    <strong>جایگاه {toPersianDigits(d.position)}</strong>
                    <span className="cell-sub" dir="ltr">
                      {d.owner === "bot" ? "آزمایشی" : d.phone}
                    </span>
                  </td>
                  <td>{planTitle(d.planId)}</td>
                  <td className="num">{formatNumber(d.months)}</td>
                  <td className="num danger-text">{formatCompact(d.amount)}</td>
                  <td>{formatWhen(d.since)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
