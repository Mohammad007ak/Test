import { useEffect, useState } from "react";
import { AlertTriangle, CalendarClock, ChevronLeft, Clock3, Landmark, RotateCcw, Users, Wallet } from "lucide-react";
import { PageSkeleton } from "../../ui/bits.jsx";
import { api } from "../../lib/api.js";
import { formatCompact, formatNumber } from "../../lib/format.js";
import { formatDay } from "../../lib/jalali.js";
import SmsCard from "./SmsCard.jsx";
import { METHOD, describeEvent, eventTone, formatDuration, formatWhen, planTitle, toman } from "./shared.jsx";

const DAY = 24 * 60 * 60 * 1000;

function Kpi({ icon: Icon, label, value, sub, tone = "", title }) {
  return (
    <div className={`kpi ${tone}`} title={title}>
      <div className="kpi-label">
        <Icon size={16} /> {label}
      </div>
      <strong className="kpi-value">{value}</strong>
      {sub && <span className="kpi-sub">{sub}</span>}
    </div>
  );
}

// One hue, one bar per category, value labelled at the end; the category's
// share is also in the tooltip. Magnitude only, so no categorical colors.
function BarList({ rows }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  const total = rows.reduce((t, r) => t + r.value, 0) || 1;
  return (
    <ul className="bar-list">
      {rows.map((r) => (
        <li
          key={r.key}
          title={`${r.label}: ${toman(r.value)}، ${formatNumber(r.count)} قسط، ${formatNumber(Math.round((r.value / total) * 100))}٪`}
        >
          <span className="bar-label">{r.label}</span>
          <span className="bar-track">
            <span className={`bar-fill ${r.tone ?? ""}`} style={{ width: `${(r.value / max) * 100}%` }} />
          </span>
          <span className="bar-value">
            {formatCompact(r.value)}
            <small>{formatNumber(r.count)} قسط</small>
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function Dashboard({ open }) {
  const [data, setData] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api("GET", "/api/ops/overview").then(setData, setError);
    api("GET", "/api/ops/events?limit=8").then(
      (r) => setEvents(r.events),
      () => {},
    );
  }, []);

  if (error) return <p className="error-text">{error.message}</p>;
  if (!data) return <PageSkeleton />;

  const { money, collection, fill, circles } = data;
  const methods = ["entry", "manual", "wallet", "guarantee"].map((k) => ({
    key: k,
    label: METHOD[k],
    value: collection.byMethod[k]?.amount ?? 0,
    count: collection.byMethod[k]?.count ?? 0,
    tone: k === "guarantee" ? "danger" : "",
  }));

  return (
    <div className="admin-grid">
      <div className="kpi-grid">
        <Kpi
          icon={Users}
          label="کاربران در طرح‌ها"
          value={formatNumber(data.people.users)}
          sub={`${formatNumber(data.people.seats)} جایگاه`}
        />
        <Kpi
          icon={CalendarClock}
          label="دوره‌های فعال"
          value={formatNumber(circles.active)}
          sub={`${formatNumber(circles.forming)} گروه در حال تکمیل، ${formatNumber(circles.completed)} پایان‌یافته`}
        />
        <Kpi
          icon={Wallet}
          label="جمع اقساط اعضا"
          value={formatCompact(money.collectedByMembers)}
          sub="تومان، بدون ضمانت"
          title={toman(money.collectedByMembers)}
        />
        <Kpi
          icon={Landmark}
          label="پرداخت به برندگان"
          value={formatCompact(money.paidOutToMembers)}
          sub={`+ ${formatCompact(money.paidOutToOperator)} سهم دیجی‌پی، ${formatNumber(money.draws)} قرعه`}
          title={toman(money.paidOutToMembers)}
        />
        <Kpi
          icon={AlertTriangle}
          label="بدهی باز (ضمانت‌شده)"
          value={formatCompact(money.openDebt)}
          sub={`${formatNumber(money.debtors)} بدهکار، ${formatCompact(money.recovered)} تسویه‌شده`}
          tone={money.openDebt ? "danger" : ""}
          title={toman(money.openDebt)}
        />
        <Kpi
          icon={Wallet}
          label="وصول بدون ضمانت"
          value={collection.paidRate === null ? "—" : `${formatNumber(Math.round(collection.paidRate * 100))}٪`}
          sub={`از ${formatNumber(collection.installments)} قسط`}
          tone={collection.paidRate !== null && collection.paidRate < 0.9 ? "gold" : ""}
        />
        <Kpi
          icon={Clock3}
          label="میانگین زمان تکمیل گروه"
          value={formatDuration(fill.averageMs)}
          sub={
            fill.count
              ? `${formatNumber(fill.underFiveMinutes)} از ${formatNumber(fill.count)} گروه زیر ۵ دقیقه`
              : "هنوز گروهی شروع نشده"
          }
        />
        <Kpi
          icon={RotateCcw}
          label="بازگشت وجه"
          value={formatCompact(money.refunds)}
          sub="تومان، خروج از صف یا انقضا"
          title={toman(money.refunds)}
        />
      </div>

      <section className="card">
        <div className="section-title">
          <h2>اقساط از کجا آمده‌اند</h2>
          <span className="muted small">مبلغ به تومان</span>
        </div>
        <BarList rows={methods} />
        <p className="muted small" style={{ marginTop: 12 }}>
          سهم ماهانه‌ی خود دیجی‌پی در این آمار نیست. ضمانت یعنی دیجی‌پی به‌جای عضو پرداخت کرده و عضو بدهکار است.
        </p>
      </section>

      <section className="card">
        <div className="section-title">
          <h2>قرعه‌های پیش رو</h2>
        </div>
        {data.upcoming.length === 0 ? (
          <p className="muted small">دوره‌ی فعالی نیست.</p>
        ) : (
          <ul className="rows compact">
            {data.upcoming.map((u) => (
              <li key={u.id}>
                <button className="row" onClick={() => open("ops", "circles", u.id)}>
                  <div className="row-main">
                    <strong>
                      {planTitle(u.planId)}، ماه {formatNumber(u.month)}
                    </strong>
                    <span>
                      {formatDay(u.at)}،{" "}
                      {u.at <= Date.now() ? "امروز" : `${formatNumber(Math.ceil((u.at - Date.now()) / DAY))} روز دیگر`}
                    </span>
                  </div>
                  <ChevronLeft size={18} className="muted" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card flush">
        <div className="section-title">
          <h2>طرح‌ها</h2>
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>طرح</th>
                <th>در حال تکمیل</th>
                <th>فعال</th>
                <th>پایان‌یافته</th>
                <th>منقضی</th>
              </tr>
            </thead>
            <tbody>
              {data.plans.map((p) => (
                <tr key={p.id}>
                  <td>
                    <strong>{p.title}</strong>
                    <span className="cell-sub">
                      {formatNumber(p.size)} نفر، قسط {formatCompact(p.share)}
                    </span>
                  </td>
                  <td className="num">{formatNumber(p.forming)}</td>
                  <td className="num">{formatNumber(p.active)}</td>
                  <td className="num">{formatNumber(p.completed)}</td>
                  <td className="num">{formatNumber(p.expired)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <div className="section-title">
          <h2>آخرین رویدادها</h2>
          <button className="link-btn" onClick={() => open("ops", "events", undefined, { replace: true })}>
            همه‌ی رویدادها
          </button>
        </div>
        {events.length === 0 ? (
          <p className="muted small">هنوز رویدادی ثبت نشده.</p>
        ) : (
          <ul className="event-list">
            {events.map((e) => (
              <li key={e.id} className={eventTone(e.kind)}>
                <span className="event-dot" />
                <div>
                  <strong>{describeEvent(e)}</strong>
                  <span>
                    {planTitle(e.planId)}، {formatWhen(e.at)}
                  </span>
                </div>
                {e.amount ? <b className="event-amount">{formatCompact(e.amount)}</b> : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <SmsCard />

      <section className="card">
        <div className="section-title">
          <h2>صندوق‌های خانوادگی (رایگان)</h2>
        </div>
        <div className="admin-stats">
          <div>
            <span>صندوق</span>
            <strong>{formatNumber(data.family.funds)}</strong>
          </div>
          <div>
            <span>عضو ثبت‌شده با شماره</span>
            <strong>{formatNumber(data.family.members)}</strong>
          </div>
        </div>
      </section>
    </div>
  );
}
