import { useEffect, useState } from "react";
import { ChevronLeft, CloudUpload, LogOut, Plus, Sparkles, Users, WalletCards } from "lucide-react";
import CreateFundWizard from "./CreateFundWizard.jsx";
import PlansSection from "./circles/PlansSection.jsx";
import { Logo } from "../ui/Logo.jsx";
import CoinCrowd from "../ui/CoinCrowd.jsx";
import { EmptyState, Segmented, Skeleton } from "../ui/bits.jsx";
import { useToast } from "../ui/feedback.jsx";
import { api } from "../lib/api.js";
import { createDemoState } from "../lib/demo.js";
import { clearLegacyState, loadLegacyState } from "../lib/storage.js";
import { formatCompact, formatNumber } from "../lib/format.js";
import { planById } from "../lib/plans.js";
import { toPersianDigits } from "../lib/jalali.js";

function greeting() {
  const hour = Number(
    new Intl.DateTimeFormat("en-US", { hour: "numeric", hourCycle: "h23", timeZone: "Asia/Tehran" }).format(new Date()),
  );
  if (hour < 5) return "شب بخیر";
  if (hour < 12) return "صبح بخیر";
  if (hour < 17) return "روز بخیر";
  return "عصر بخیر";
}

// The banner's crowd is the member's own group: one figure per seat of their
// running plan (or the one still filling up), a check over each who's been paid.
function crowdOf(tab, circles) {
  if (tab === "family")
    return { title: "صندوق فامیلی، بدون دفترچه", text: "سهم‌ها، قرعه و وام‌ها را آنلاین با هم ببینید." };
  const circle = circles?.find((c) => c.status === "active") ?? circles?.find((c) => c.status === "forming");
  // Not in a plan yet: just you and Digi Gharz.
  if (!circle)
    return {
      title: "با هم، زودتر به پول برسید",
      text: "هر ماه یکی از جمع، کل مبلغ را یک‌جا می‌گیرد.",
      count: 2,
      cast: ["plain", "logo"],
    };
  const title = planById(circle.planId)?.title ?? "طرح شما";
  // Seat 1 is always Digi Gharz; seats fill in from the right, so it goes last.
  const cast = Array.from({ length: circle.size }, (_, i) => (i === circle.size - 1 ? "logo" : "plain"));
  if (circle.status === "forming")
    return {
      title,
      text: `${formatNumber(circle.taken)} نفر از ${formatNumber(circle.size)} نفر آمده‌اند؛ گروه در حال تکمیل است.`,
      count: circle.size,
      present: circle.taken,
      cast,
    };
  return {
    title,
    text: `${formatNumber(circle.received)} نفر از ${formatNumber(circle.size)} نفر وامشان را گرفته‌اند.`,
    count: circle.size,
    done: circle.received,
    cast,
  };
}

export default function FundList({ phone, tab, setTab, open, onLogout }) {
  const [funds, setFunds] = useState(null);
  const [error, setError] = useState(null);
  const [creating, setCreating] = useState(false);
  const [circles, setCircles] = useState(null);
  const [legacy, setLegacy] = useState(loadLegacyState);
  const toast = useToast();

  useEffect(() => {
    api("GET", "/api/funds").then(setFunds, setError);
    api("GET", "/api/circles").then(
      (r) => setCircles(r.circles),
      () => setCircles([]),
    );
  }, []);

  const create = async (data, message = "صندوق ساخته شد") => {
    try {
      const { id } = await api("POST", "/api/funds", { data });
      toast(message);
      open("manage", id);
      return true;
    } catch (e) {
      toast(e.message, { tone: "error" });
      return false;
    }
  };

  const migrateLegacy = async () => {
    if (await create(legacy, "صندوق به حسابتان منتقل شد")) {
      clearLegacyState();
      setLegacy(null);
    }
  };

  const nothingYet = funds && funds.managed.length === 0 && funds.member.length === 0;

  return (
    <div className="home">
      <header className="appbar">
        <Logo />
        <div className="appbar-title" />
        <span className="muted small desktop-only" dir="ltr">
          {toPersianDigits(phone)}
        </span>
        <button className="icon-btn" onClick={onLogout} aria-label="خروج" title="خروج">
          <LogOut size={20} />
        </button>
      </header>

      <div className="page">
        <CoinCrowd {...crowdOf(tab, circles)} />
        <div className="page-head">
          <div>
            <h1>{greeting()} 👋</h1>
            <p>
              {tab === "plans"
                ? "طرح‌های تضمینی با مدیریت و ضمانت دیجی‌پی."
                : "صندوق‌های خانوادگی‌ای که مدیر یا عضو آن‌ها هستید."}
            </p>
          </div>
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { value: "plans", label: "طرح‌های تضمینی" },
              { value: "family", label: "صندوق خانوادگی" },
            ]}
          />
        </div>

        {tab === "plans" && <PlansSection open={open} />}

        {tab === "family" && (
          <>
            {error && <p className="error-text">{error.message}</p>}

            {legacy && (
              <div className="banner">
                <CloudUpload size={24} />
                <div>
                  <strong>«{legacy.fund.name}» فقط روی این مرورگر است</strong>
                  <p>آن را به حسابتان منتقل کنید تا از هر دستگاهی در دسترس باشد و اعضا هم ببینند.</p>
                </div>
                <button className="btn primary sm" onClick={migrateLegacy}>
                  انتقال
                </button>
              </div>
            )}

            {!funds && !error && (
              <div className="fund-grid">
                <Skeleton height={150} radius={20} />
                <Skeleton height={150} radius={20} />
              </div>
            )}

            {nothingYet && (
              <div className="card">
                <EmptyState
                  title="اولین صندوقتان را بسازید"
                  text="در کمتر از یک دقیقه صندوق را تعریف کنید، اعضا را اضافه کنید و قرعه‌کشی را شروع کنید."
                  action={
                    <div className="stack-sm">
                      <button className="btn primary lg" onClick={() => setCreating(true)}>
                        <Plus size={20} /> ساخت صندوق
                      </button>
                      <button className="btn ghost" onClick={() => create(createDemoState(), "صندوق نمونه ساخته شد")}>
                        <Sparkles size={18} /> اول با یک صندوق نمونه امتحان کنم
                      </button>
                    </div>
                  }
                />
              </div>
            )}

            {funds && !nothingYet && (
              <>
                <section>
                  <div className="section-title">
                    <h2>{funds.managed.length ? "مدیریت می‌کنید" : "صندوق خودتان را بسازید"}</h2>
                  </div>
                  <div className="fund-grid">
                    {funds.managed.map((fund) => (
                      <button key={fund.id} className="fund-card" onClick={() => open("manage", fund.id)}>
                        <div className="fund-card-top">
                          <span className="fund-mark">
                            <WalletCards size={22} />
                          </span>
                          <div>
                            <strong>{fund.name}</strong>
                            <span>مدیر صندوق</span>
                          </div>
                          <ChevronLeft size={20} className="muted" />
                        </div>
                        <div className="fund-card-stats">
                          <div>
                            <span>موجودی</span>
                            <strong className="num">{formatCompact(fund.balance)}</strong>
                          </div>
                          <div>
                            <span>اعضا</span>
                            <strong className="num">{formatNumber(fund.members)}</strong>
                          </div>
                          <div>
                            <span>بدهکار</span>
                            <strong className="num" style={{ color: fund.lateMembers ? "var(--danger)" : undefined }}>
                              {fund.lateMembers ? `${formatNumber(fund.lateMembers)} نفر` : "ندارد"}
                            </strong>
                          </div>
                        </div>
                      </button>
                    ))}
                    <button className="fund-card add" onClick={() => setCreating(true)}>
                      <Plus size={24} />
                      صندوق جدید
                    </button>
                  </div>
                </section>

                {funds.member.length > 0 && (
                  <section>
                    <div className="section-title">
                      <h2>عضو هستید</h2>
                    </div>
                    <div className="fund-grid">
                      {funds.member.map((fund) => (
                        <button key={fund.id} className="fund-card member" onClick={() => open("view", fund.id)}>
                          <div className="fund-card-top">
                            <span className="fund-mark">
                              <Users size={22} />
                            </span>
                            <div>
                              <strong>{fund.name}</strong>
                              <span>عضو صندوق</span>
                            </div>
                            <ChevronLeft size={20} className="muted" />
                          </div>
                        </button>
                      ))}
                    </div>
                  </section>
                )}
              </>
            )}
          </>
        )}
      </div>

      <CreateFundWizard open={creating} onClose={() => setCreating(false)} onCreate={create} />
    </div>
  );
}
