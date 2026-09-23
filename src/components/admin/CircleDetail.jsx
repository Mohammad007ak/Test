import { useCallback, useEffect, useState } from "react";
import { Trophy } from "lucide-react";
import AppBar from "../../ui/AppBar.jsx";
import { PageSkeleton } from "../../ui/bits.jsx";
import { api } from "../../lib/api.js";
import { formatCompact, formatNumber } from "../../lib/format.js";
import { formatDay, toPersianDigits } from "../../lib/jalali.js";
import { CircleActions, useCircleActions } from "./Circles.jsx";
import { StatusBadge, describeEvent, eventTone, formatDuration, formatWhen } from "./shared.jsx";

// Each cell of the members × months grid: how that installment was paid.
const CELL = {
  entry: { text: "عضویت", tone: "ok" },
  manual: { text: "درگاه", tone: "ok" },
  wallet: { text: "کیف پول", tone: "ok" },
  operator: { text: "دیجی‌پی", tone: "op" },
  guarantee: { text: "ضمانت", tone: "bad" },
};

function cellOf(p) {
  if (!p) return { text: "", tone: "future" };
  if (p.status === "due") return { text: "باز", tone: "due" };
  if (p.status === "settled") return { text: "تسویه", tone: "settled" };
  return CELL[p.method] ?? { text: p.method, tone: "ok" };
}

const OWNER = { operator: "دیجی‌پی", bot: "آزمایشی", member: "" };

export default function CircleDetail({ id, back }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [allEvents, setAllEvents] = useState(false);
  const load = useCallback(() => api("GET", `/api/ops/circles/${id}`).then(setData, setError), [id]);
  useEffect(() => {
    load();
  }, [load]);
  const actions = useCircleActions(load);

  const header = <AppBar onBack={back} title={data?.circle.title ?? "دوره"} sub="جزئیات دوره" />;
  if (error)
    return (
      <>
        {header}
        <p className="error-text">{error.message}</p>
      </>
    );
  if (!data)
    return (
      <>
        {header}
        <PageSkeleton />
      </>
    );

  const { circle, members, draws, events } = data;
  const months = Array.from({ length: circle.months }, (_, i) => i + 1);

  return (
    <>
      {header}
      <div className="admin-grid">
        <section className="card span-2">
          <div className="detail-head">
            <div className="admin-stats">
              <div>
                <span>وضعیت</span>
                <StatusBadge status={circle.status} />
              </div>
              <div>
                <span>اعضا</span>
                <strong>
                  {formatNumber(members.length)} / {formatNumber(circle.size)}
                </strong>
              </div>
              <div>
                <span>ماه جاری</span>
                <strong>
                  {circle.status === "forming"
                    ? "—"
                    : `${formatNumber(circle.currentMonth)} / ${formatNumber(circle.months)}`}
                </strong>
              </div>
              <div>
                <span>مبلغ هر ماه</span>
                <strong>{formatCompact(circle.pot)}</strong>
              </div>
              <div>
                <span>{circle.startedAt ? "زمان تکمیل گروه" : "مهلت تکمیل"}</span>
                <strong>
                  {circle.startedAt ? formatDuration(circle.startedAt - circle.createdAt) : formatWhen(circle.deadline)}
                </strong>
              </div>
            </div>
            <CircleActions circle={circle} actions={actions} />
          </div>
        </section>

        <section className="card flush span-2">
          <div className="section-title">
            <h2>اقساط اعضا، ماه به ماه</h2>
            <div className="legend">
              <span className="cell ok">پرداخت</span>
              <span className="cell due">باز</span>
              <span className="cell bad">ضمانت</span>
              <span className="cell settled">تسویه</span>
            </div>
          </div>
          <div className="table-scroll">
            <table className="data-table matrix">
              <thead>
                <tr>
                  <th>جایگاه</th>
                  <th>برنده‌ی ماه</th>
                  <th>بدهی</th>
                  {months.map((m) => (
                    <th
                      key={m}
                      className="num"
                      title={circle.schedule[m - 1] ? formatDay(circle.schedule[m - 1].drawAt) : ""}
                    >
                      {formatNumber(m)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <strong>{toPersianDigits(m.position)}</strong>
                      <span className="cell-sub" dir="ltr">
                        {OWNER[m.owner] || m.phone}
                      </span>
                    </td>
                    <td className="num">
                      {m.wonMonth ? (
                        <span className="won">
                          <Trophy size={13} /> {formatNumber(m.wonMonth)}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className={`num ${m.debt ? "danger-text" : ""}`}>{m.debt ? formatCompact(m.debt) : "—"}</td>
                    {months.map((month) => {
                      const c = cellOf(m.payments[month]);
                      return (
                        <td key={month} className="num">
                          {c.text && <span className={`cell ${c.tone}`}>{c.text}</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card flush">
          <div className="section-title">
            <h2>قرعه‌ها و واریزها</h2>
          </div>
          {draws.length === 0 ? (
            <p className="muted small padded">هنوز قرعه‌ای انجام نشده.</p>
          ) : (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ماه</th>
                    <th>برنده</th>
                    <th>نوع</th>
                    <th>مبلغ</th>
                    <th>واریز</th>
                  </tr>
                </thead>
                <tbody>
                  {draws.map((d) => (
                    <tr key={d.month}>
                      <td className="num">{formatNumber(d.month)}</td>
                      <td>{d.kind === "operator" ? "دیجی‌پی" : `جایگاه ${toPersianDigits(d.winnerPosition)}`}</td>
                      <td>
                        {d.kind === "operator"
                          ? "سهم مدیر"
                          : d.kind === "last"
                            ? "آخرین نفر"
                            : `قرعه بین ${formatNumber(d.eligible)} نفر`}
                      </td>
                      <td className="num">{formatCompact(d.pot)}</td>
                      <td>
                        {d.paidOut ? (
                          <span className="badge success">انجام شد</span>
                        ) : (
                          <span className="badge gold">در انتظار</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="card">
          <div className="section-title">
            <h2>رویدادهای این دوره</h2>
          </div>
          <ul className="event-list">
            {(allEvents ? events : events.slice(0, 15)).map((e) => (
              <li key={e.id} className={eventTone(e.kind)}>
                <span className="event-dot" />
                <div>
                  <strong>{describeEvent(e)}</strong>
                  <span>
                    {formatWhen(e.at)}
                    {e.position ? `، جایگاه ${toPersianDigits(e.position)}` : ""}
                  </span>
                </div>
                {e.amount ? <b className="event-amount">{formatCompact(e.amount)}</b> : null}
              </li>
            ))}
          </ul>
          {!allEvents && events.length > 15 && (
            <button className="btn ghost block" onClick={() => setAllEvents(true)}>
              نمایش همه‌ی {formatNumber(events.length)} رویداد
            </button>
          )}
        </section>
      </div>
    </>
  );
}
