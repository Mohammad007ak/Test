import { useCallback, useEffect, useState } from "react";
import { Eye, FastForward, FlaskConical, Users } from "lucide-react";
import AppBar from "../../ui/AppBar.jsx";
import { EmptyState, PageSkeleton, Spinner } from "../../ui/bits.jsx";
import { useToast } from "../../ui/feedback.jsx";
import { api } from "../../lib/api.js";
import { planById } from "../../lib/plans.js";
import { formatNumber } from "../../lib/format.js";

const STATUS = {
  forming: "در حال تکمیل",
  active: "فعال",
  completed: "پایان‌یافته",
};

// Operator tools. In production the monthly close runs on a schedule; here
// it's a button so a whole circle can be walked through in a demo.
export default function Ops({ back, open }) {
  const [circles, setCircles] = useState(null);
  const [busy, setBusy] = useState(null);
  const toast = useToast();

  const load = useCallback(() => api("GET", "/api/ops/circles").then((r) => setCircles(r.circles)), []);
  useEffect(() => {
    load().catch((e) => toast(e.message, { tone: "error" }));
  }, [load, toast]);

  const run = async (id, action, message) => {
    setBusy(id + action);
    try {
      const result = await api("POST", `/api/ops/circles/${id}/${action}`);
      toast(typeof message === "function" ? message(result) : message);
      await load();
    } catch (e) {
      toast(e.message, { tone: "error" });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="home">
      <AppBar
        onBack={back}
        title="پنل عملیات"
        sub={
          <>
            <FlaskConical size={13} /> شبیه‌ساز دیجی‌پی
          </>
        }
      />
      <div className="page">
        <div className="inline-note">
          <FlaskConical size={16} />
          <span>
            در نسخه‌ی واقعی، بستن ماه (برداشت خودکار، ضمانت معوقه‌ها، قرعه و واریز پات) زمان‌بندی‌شده اجرا می‌شود. اینجا
            با دکمه انجامش می‌دهید. اعضای شبیه‌سازی‌شده‌ی هر چهارم پرداخت نمی‌کنند تا ضمانت را ببینید.
          </span>
        </div>
        {!circles ? (
          <PageSkeleton />
        ) : circles.length === 0 ? (
          <section className="card">
            <EmptyState
              icon={Users}
              title="هنوز دوره‌ای ساخته نشده"
              text="با عضویت در یک طرح، اولین دوره ساخته می‌شود."
            />
          </section>
        ) : (
          <section className="card flush">
            <ul className="rows">
              {circles.map((c) => (
                <li key={c.id} className="row" style={{ flexWrap: "wrap" }}>
                  <div className="row-main">
                    <strong>{planById(c.planId)?.title}</strong>
                    <span>
                      {STATUS[c.status]}،{" "}
                      {c.status === "forming"
                        ? `${formatNumber(c.taken)} از ${formatNumber(c.size)} نفر`
                        : `ماه ${formatNumber(c.currentMonth)} از ${formatNumber(c.months)}`}
                    </span>
                  </div>
                  <div className="row-end">
                    <button className="icon-btn sm soft" onClick={() => open("circle", c.id)} aria-label="مشاهده">
                      <Eye size={16} />
                    </button>
                    {c.status === "forming" && (
                      <button
                        className="btn sm outline"
                        onClick={() => run(c.id, "fill", "دوره تکمیل و شروع شد")}
                        disabled={Boolean(busy)}
                      >
                        {busy === c.id + "fill" ? <Spinner /> : <Users size={15} />} تکمیل با اعضای آزمایشی
                      </button>
                    )}
                    {c.status === "active" && (
                      <button
                        className="btn sm primary"
                        onClick={() => run(c.id, "close-month", (r) => `ماه ${formatNumber(r.month)} بسته شد`)}
                        disabled={Boolean(busy)}
                      >
                        {busy === c.id + "close-month" ? <Spinner /> : <FastForward size={15} />} بستن ماه{" "}
                        {formatNumber(c.currentMonth)}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
