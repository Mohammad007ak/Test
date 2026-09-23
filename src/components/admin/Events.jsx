import { useEffect, useState } from "react";
import { ScrollText } from "lucide-react";
import { EmptyState, PageSkeleton } from "../../ui/bits.jsx";
import { api } from "../../lib/api.js";
import { formatCompact } from "../../lib/format.js";
import { toPersianDigits } from "../../lib/jalali.js";
import { EVENT_KINDS, describeEvent, eventTone, formatWhen, planTitle } from "./shared.jsx";

// The audit trail: every money movement and lifecycle step, newest first.
export default function Events({ open }) {
  const [kind, setKind] = useState("");
  const [events, setEvents] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    setEvents(null);
    api("GET", `/api/ops/events?limit=300${kind ? `&kind=${kind}` : ""}`).then((r) => setEvents(r.events), setError);
  }, [kind]);

  return (
    <div className="stack">
      <div className="filters">
        <div className="input sm">
          <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="نوع رویداد">
            <option value="">همه‌ی رویدادها</option>
            {EVENT_KINDS.map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {error ? (
        <p className="error-text">{error.message}</p>
      ) : !events ? (
        <PageSkeleton />
      ) : events.length === 0 ? (
        <section className="card">
          <EmptyState icon={ScrollText} title="رویدادی نیست" text="با فعالیت کاربران، رویدادها اینجا ثبت می‌شوند." />
        </section>
      ) : (
        <section className="card">
          <ul className="event-list">
            {events.map((e) => (
              <li
                key={e.id}
                className={`${eventTone(e.kind)} ${e.circleId ? "clickable" : ""}`}
                onClick={() => e.circleId && open("ops", "circles", e.circleId)}
              >
                <span className="event-dot" />
                <div>
                  <strong>{describeEvent(e)}</strong>
                  <span>
                    {[
                      planTitle(e.planId),
                      formatWhen(e.at),
                      e.position ? `جایگاه ${toPersianDigits(e.position)}` : null,
                      e.phone,
                    ]
                      .filter(Boolean)
                      .join("، ")}
                  </span>
                </div>
                {e.amount ? <b className="event-amount">{formatCompact(e.amount)}</b> : null}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
