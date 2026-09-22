import { useEffect, useState } from "react";
import { ChevronLeft, CloudUpload, Landmark, LogOut, Plus, Sparkles, Users, WalletCards } from "lucide-react";
import CreateFundWizard from "./CreateFundWizard.jsx";
import { Logo } from "../ui/Logo.jsx";
import { EmptyState, Skeleton } from "../ui/bits.jsx";
import { useToast } from "../ui/feedback.jsx";
import { api } from "../lib/api.js";
import { createDemoState } from "../lib/demo.js";
import { clearLegacyState, loadLegacyState } from "../lib/storage.js";
import { formatCompact, formatNumber } from "../lib/format.js";
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

export default function FundList({ phone, open, onLogout }) {
  const [funds, setFunds] = useState(null);
  const [error, setError] = useState(null);
  const [creating, setCreating] = useState(false);
  const [legacy, setLegacy] = useState(loadLegacyState);
  const toast = useToast();

  useEffect(() => {
    api("GET", "/api/funds").then(setFunds, setError);
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
        <div className="page-head">
          <div>
            <h1>{greeting()} 👋</h1>
            <p>صندوق‌هایی که مدیر یا عضو آن‌ها هستید.</p>
          </div>
        </div>

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
              icon={Landmark}
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
                <h2>مدیریت می‌کنید</h2>
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
      </div>

      <CreateFundWizard open={creating} onClose={() => setCreating(false)} onCreate={create} />
    </div>
  );
}
