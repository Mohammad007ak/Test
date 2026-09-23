import { useEffect, useState } from "react";
import { ChevronLeft, Hourglass, ShieldCheck, Trophy, Users, Wrench } from "lucide-react";
import JoinSheet from "./JoinSheet.jsx";
import { Skeleton } from "../../ui/bits.jsx";
import { api } from "../../lib/api.js";
import { planById } from "../../lib/plans.js";
import { formatCompact, formatNumber } from "../../lib/format.js";

function CircleStatus({ c }) {
  if (c.status === "forming") {
    return (
      <span className="badge">
        <Hourglass size={12} /> {formatNumber(c.taken)} از {formatNumber(c.size)} نفر
      </span>
    );
  }
  if (c.status === "completed") return <span className="badge">پایان‌یافته</span>;
  if (c.owed) return <span className="badge danger">{formatCompact(c.owed)} بدهی</span>;
  if (c.wonMonth) return <span className="badge gold">دریافت کرده‌اید</span>;
  return (
    <span className="badge brand">
      ماه {formatNumber(c.currentMonth)} از {formatNumber(c.months)}
    </span>
  );
}

export default function PlansSection({ open }) {
  const [plans, setPlans] = useState(null);
  const [mine, setMine] = useState(null);
  const [ops, setOps] = useState(false);
  const [joining, setJoining] = useState(null);

  useEffect(() => {
    api("GET", "/api/plans").then((r) => setPlans(r.plans));
    api("GET", "/api/circles").then((r) => {
      setMine(r.circles);
      setOps(r.ops);
    });
  }, []);

  return (
    <div className="page">
      {mine?.length > 0 && (
        <section>
          <div className="section-title">
            <h2>دوره‌های من</h2>
          </div>
          <div className="fund-grid">
            {mine.map((c) => (
              <button key={c.id} className="fund-card" onClick={() => open("circle", c.id)}>
                <div className="fund-card-top">
                  <span className="fund-mark">{c.wonMonth ? <Trophy size={22} /> : <Users size={22} />}</span>
                  <div>
                    <strong>{planById(c.planId)?.title}</strong>
                    <span>
                      سهم {formatCompact(c.share)}، پات {formatCompact(c.pot)}
                    </span>
                  </div>
                  <ChevronLeft size={20} className="muted" />
                </div>
                <CircleStatus c={c} />
              </button>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="section-title">
          <h2>طرح‌های تضمینی</h2>
          <span className="badge brand">
            <ShieldCheck size={13} /> با ضمانت دیجی‌پی
          </span>
        </div>
        <p className="muted small" style={{ marginBottom: 14 }}>
          صندوق با آدم‌های اعتبارسنجی‌شده؛ دیجی‌پی مدیریت و ضمانت اقساط را بر عهده دارد و قرعه‌ها برای همه قابل بررسی
          است.
        </p>
        {!plans ? (
          <div className="plan-grid">
            <Skeleton height={220} radius={20} />
            <Skeleton height={220} radius={20} />
            <Skeleton height={220} radius={20} />
          </div>
        ) : (
          <div className="plan-grid">
            {plans.map((p, i) => (
              <article key={p.id} className={`plan-card ${i === 1 ? "featured" : ""}`}>
                {i === 1 && <span className="plan-flag">پرطرفدار</span>}
                <h3>{p.title}</h3>
                <div className="plan-pot">
                  <span>دریافت یک‌جا</span>
                  <strong>{formatCompact(p.pot)}</strong>
                  <small>تومان</small>
                </div>
                <ul className="plan-facts">
                  <li>
                    <span>سهم ماهانه</span>
                    <b>{formatCompact(p.share)} تومان</b>
                  </li>
                  <li>
                    <span>مدت</span>
                    <b>{formatNumber(p.months)} ماه</b>
                  </li>
                  <li>
                    <span>اعضا</span>
                    <b>{formatNumber(p.size)} نفر</b>
                  </li>
                </ul>
                <div className="plan-fill">
                  <div className="bar">
                    <div style={{ width: `${(p.taken / p.size) * 100}%` }} />
                  </div>
                  <span>
                    دوره‌ی بعدی: {formatNumber(p.taken)} از {formatNumber(p.size)} جا پر شده
                  </span>
                </div>
                <button className={`btn ${i === 1 ? "primary" : "outline"} block`} onClick={() => setJoining(p)}>
                  دریافت
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      {ops && (
        <button className="btn ghost" onClick={() => open("ops")}>
          <Wrench size={18} /> پنل عملیات و شبیه‌ساز
        </button>
      )}

      <JoinSheet
        plan={joining}
        onClose={() => setJoining(null)}
        onCheckout={(checkoutId) => {
          setJoining(null);
          open("checkout", checkoutId);
        }}
      />
    </div>
  );
}
