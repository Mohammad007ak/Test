import { useEffect, useState } from "react";
import FundForm from "./FundForm.jsx";
import { api } from "../lib/api.js";
import { createEmptyState } from "../lib/fund.js";
import { createDemoState } from "../lib/demo.js";
import { clearLegacyState, loadLegacyState } from "../lib/storage.js";
import { formatNumber } from "../lib/format.js";
import { toPersianDigits } from "../lib/jalali.js";

export default function FundList({ phone, open, onLogout }) {
  const [funds, setFunds] = useState(null);
  const [error, setError] = useState(null);
  const [creating, setCreating] = useState(false);
  const [legacy, setLegacy] = useState(loadLegacyState);

  useEffect(() => {
    api("GET", "/api/funds").then(setFunds, setError);
  }, []);

  const create = async (data) => {
    try {
      const { id } = await api("POST", "/api/funds", { data });
      open("manage", id);
      return true;
    } catch (e) {
      alert(e.message);
      return false;
    }
  };

  const migrateLegacy = async () => {
    if (await create(legacy)) {
      clearLegacyState();
      setLegacy(null);
    }
  };

  return (
    <div className="stack">
      <header className="topbar">
        <div>
          <h1>صندوق‌های من</h1>
          <span className="muted" dir="ltr">{toPersianDigits(phone)}</span>
        </div>
        <button className="btn ghost small" onClick={onLogout}>
          خروج
        </button>
      </header>

      {error && <p className="danger">{error.message}</p>}
      {!funds && !error && <p className="empty">در حال بارگذاری…</p>}

      {legacy && (
        <section className="card notice-card">
          <h2>صندوق «{legacy.fund.name}» روی این مرورگر ذخیره شده</h2>
          <p className="muted">آن را به حسابتان منتقل کنید تا از هر دستگاهی در دسترس باشد و اعضا هم ببینند.</p>
          <button className="btn primary" onClick={migrateLegacy}>
            انتقال به حساب من
          </button>
        </section>
      )}

      {funds && (
        <>
          <section className="card">
            <div className="card-head">
              <h2>مدیر هستید</h2>
              {!creating && (
                <button className="btn primary" onClick={() => setCreating(true)}>
                  + صندوق جدید
                </button>
              )}
            </div>
            {creating && (
              <div className="form-box">
                <FundForm
                  submitLabel="ساخت صندوق"
                  onSave={(fund) => create({ ...createEmptyState(), fund })}
                />
                <button className="btn ghost wide" onClick={() => setCreating(false)}>
                  انصراف
                </button>
              </div>
            )}
            {funds.managed.length === 0 && !creating ? (
              <div className="empty">
                <p>هنوز صندوقی نساخته‌اید.</p>
                <button className="btn ghost" onClick={() => create(createDemoState())}>
                  ساخت صندوق نمونه با اطلاعات آزمایشی
                </button>
              </div>
            ) : (
              <ul className="list">
                {funds.managed.map((fund) => (
                  <li key={fund.id}>
                    <div>
                      <strong>{fund.name}</strong>
                      <span className="muted">{formatNumber(fund.members)} عضو</span>
                    </div>
                    <button className="btn small primary" onClick={() => open("manage", fund.id)}>
                      مدیریت ←
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card">
            <div className="card-head">
              <h2>عضو هستید</h2>
            </div>
            {funds.member.length === 0 ? (
              <p className="empty">
                وقتی مدیر یک صندوق شماره‌ی شما را ثبت کند، آن صندوق اینجا نشان داده می‌شود.
              </p>
            ) : (
              <ul className="list">
                {funds.member.map((fund) => (
                  <li key={fund.id}>
                    <strong>{fund.name}</strong>
                    <button className="btn small" onClick={() => open("view", fund.id)}>
                      مشاهده ←
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
