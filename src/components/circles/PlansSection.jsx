import { useEffect, useState } from "react";
import { ChevronLeft, Hourglass, ShieldCheck, Sparkles, Trophy, Users, Wrench } from "lucide-react";
import JoinSheet from "./JoinSheet.jsx";
import { Figure } from "../../ui/Figure.jsx";
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

// One plan: the group itself up top (Digipay's seat first), then what you get.
function PlanCard({ plan, onJoin }) {
  const short = plan.months <= 6;
  const premium = plan.share >= 10_000_000;
  const figSize = plan.size <= 6 ? 50 : 30;
  return (
    <article className={`plan-card ${short ? "short" : "long"}`}>
      <header className="plan-head">
        <div className="plan-tags">
          <span className="plan-chip">{formatNumber(plan.months)} ماهه</span>
          {premium && (
            <span className="plan-chip premium">
              <Sparkles size={12} /> ویژه
            </span>
          )}
          {plan.flag && <span className="plan-flag">{plan.flag}</span>}
        </div>
        <div className="plan-crowd" aria-hidden="true">
          {Array.from({ length: plan.size }, (_, i) => (
            <Figure key={i} size={figSize} pose={["stand", "a", "b"][i % 3]} logo={i === 0} />
          ))}
        </div>
      </header>
      <div className="plan-body">
        <h3>{plan.title}</h3>
        <div className="plan-pot">
          <span>دریافت یک‌جا، بدون بهره</span>
          <strong>{formatCompact(plan.pot)}</strong>
          <small>تومان</small>
        </div>
        <div className="plan-tiles">
          <div>
            <small>قسط ماهانه</small>
            <b>{formatCompact(plan.share)}</b>
          </div>
          <div>
            <small>مدت</small>
            <b>{formatNumber(plan.months)} ماه</b>
          </div>
          <div>
            <small>اعضا</small>
            <b>{formatNumber(plan.size)} نفر</b>
          </div>
        </div>
        <button className={`btn ${short ? "gold" : "primary"} block`} onClick={onJoin}>
          عضویت در این طرح
        </button>
      </div>
    </article>
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
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} height={300} radius={24} />
            ))}
          </div>
        ) : (
          <div className="plan-grid">
            {plans.map((p) => (
              <PlanCard key={p.id} plan={p} onJoin={() => setJoining(p)} />
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
