import { useCallback, useEffect, useState } from "react";
import { Eye, FastForward, Users } from "lucide-react";
import { EmptyState, PageSkeleton, Segmented, Spinner } from "../../ui/bits.jsx";
import { useToast } from "../../ui/feedback.jsx";
import { api } from "../../lib/api.js";
import { PLANS } from "../../lib/plans.js";
import { formatCompact, formatNumber } from "../../lib/format.js";
import { formatDay } from "../../lib/jalali.js";
import { StatusBadge, formatWhen, planTitle } from "./shared.jsx";

// Operator actions on a circle. In production the draw runs by itself on
// its day; here it can be run early to walk a circle through in a demo.
export function useCircleActions(reload) {
  const [busy, setBusy] = useState(null);
  const toast = useToast();
  const run = async (id, action, message) => {
    setBusy(id + action);
    try {
      const result = await api("POST", `/api/ops/circles/${id}/${action}`);
      toast(typeof message === "function" ? message(result) : message);
      await reload();
    } catch (e) {
      toast(e.message, { tone: "error" });
    } finally {
      setBusy(null);
    }
  };
  return {
    busy,
    fill: (id) => run(id, "fill", "گروه با اعضای آزمایشی تکمیل و دوره شروع شد"),
    draw: (id) => run(id, "close-month", (r) => `قرعه‌ی ماه ${formatNumber(r.month)} انجام شد`),
  };
}

export function CircleActions({ circle, actions }) {
  const { busy } = actions;
  if (circle.status === "forming") {
    return (
      <button className="btn sm outline" onClick={() => actions.fill(circle.id)} disabled={Boolean(busy)}>
        {busy === circle.id + "fill" ? <Spinner /> : <Users size={15} />} تکمیل آزمایشی
      </button>
    );
  }
  if (circle.status === "active") {
    return (
      <button className="btn sm primary" onClick={() => actions.draw(circle.id)} disabled={Boolean(busy)}>
        {busy === circle.id + "close-month" ? <Spinner /> : <FastForward size={15} />} قرعه‌ی ماه{" "}
        {formatNumber(circle.currentMonth)} (الان)
      </button>
    );
  }
  return null;
}

const FILTERS = [
  { value: "all", label: "همه" },
  { value: "forming", label: "در حال تکمیل" },
  { value: "active", label: "فعال" },
  { value: "completed", label: "پایان‌یافته" },
  { value: "expired", label: "منقضی" },
];

export default function Circles({ open }) {
  const [circles, setCircles] = useState(null);
  const [status, setStatus] = useState("all");
  const [plan, setPlan] = useState("all");
  const [error, setError] = useState(null);

  const load = useCallback(() => api("GET", "/api/ops/circles").then((r) => setCircles(r.circles), setError), []);
  useEffect(() => {
    load();
  }, [load]);
  const actions = useCircleActions(load);

  if (error) return <p className="error-text">{error.message}</p>;
  if (!circles) return <PageSkeleton />;

  const shown = circles.filter(
    (c) => (status === "all" || c.status === status) && (plan === "all" || c.planId === plan),
  );

  return (
    <div className="stack">
      <div className="filters">
        <Segmented
          value={status}
          onChange={setStatus}
          options={FILTERS.map((f) => ({
            ...f,
            count: f.value === "all" ? circles.length : circles.filter((c) => c.status === f.value).length,
          }))}
        />
        <div className="input sm">
          <select value={plan} onChange={(e) => setPlan(e.target.value)} aria-label="طرح">
            <option value="all">همه‌ی طرح‌ها</option>
            {PLANS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {shown.length === 0 ? (
        <section className="card">
          <EmptyState title="دوره‌ای با این فیلتر نیست" text="فیلترها را عوض کنید." />
        </section>
      ) : (
        <section className="card flush">
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>طرح</th>
                  <th>وضعیت</th>
                  <th>اعضا</th>
                  <th>ماه</th>
                  <th>قسط این ماه</th>
                  <th>بدهی باز</th>
                  <th>قرعه‌ی بعدی / مهلت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {shown.map((c) => (
                  <tr key={c.id} className="clickable" onClick={() => open("ops", "circles", c.id)}>
                    <td>
                      <strong>{planTitle(c.planId)}</strong>
                      <span className="cell-sub">ساخته‌شده {formatWhen(c.createdAt)}</span>
                    </td>
                    <td>
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="num">
                      {formatNumber(c.taken)} / {formatNumber(c.size)}
                    </td>
                    <td className="num">
                      {c.status === "forming" ? "—" : `${formatNumber(c.currentMonth)} / ${formatNumber(c.months)}`}
                    </td>
                    <td className="num">
                      {c.thisMonth ? `${formatNumber(c.thisMonth.paid)} از ${formatNumber(c.thisMonth.of)}` : "—"}
                    </td>
                    <td className={`num ${c.debt ? "danger-text" : ""}`}>{c.debt ? formatCompact(c.debt) : "—"}</td>
                    <td>
                      {c.nextDrawAt
                        ? formatDay(c.nextDrawAt)
                        : c.status === "forming"
                          ? `مهلت تا ${formatWhen(c.deadline)}`
                          : "—"}
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="row-end">
                        <CircleActions circle={c} actions={actions} />
                        <button
                          className="icon-btn sm soft"
                          onClick={() => open("ops", "circles", c.id)}
                          aria-label="جزئیات"
                        >
                          <Eye size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
