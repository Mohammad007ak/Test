import { useRef } from "react";
import FundForm from "./FundForm.jsx";
import { api } from "../lib/api.js";
import { isValidState } from "../lib/fund.js";

export default function Settings({ state, update, server, goHome }) {
  const fileInput = useRef(null);

  const exportData = () => {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `sandogh-backup-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const importData = async (file) => {
    try {
      const data = JSON.parse(await file.text());
      if (!isValidState(data)) throw new Error("invalid");
      if (confirm("اطلاعات فعلی با فایل پشتیبان جایگزین شود؟")) update(() => data);
    } catch {
      alert("فایل پشتیبان معتبر نیست.");
    }
  };

  const deleteFund = async () => {
    const typed = prompt(`برای حذف همیشگی، اسم صندوق را بنویسید: ${state.fund.name}`);
    if (typed?.trim() !== state.fund.name) return;
    try {
      await api("DELETE", `/api/funds/${server.fundId}`);
      goHome();
    } catch (e) {
      alert(e.message);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="card-head">
          <h2>تنظیمات صندوق</h2>
        </div>
        <p className="muted">تغییر مبلغ وام یا تعداد اقساط فقط روی وام‌های بعدی اثر دارد.</p>
        <FundForm
          fund={state.fund}
          submitLabel="ذخیره‌ی تنظیمات"
          onSave={(fund) => {
            update((s) => ({ ...s, fund }));
            alert("ذخیره شد.");
          }}
        />
      </section>

      <section className="card">
        <div className="card-head">
          <h2>پشتیبان‌گیری</h2>
        </div>
        <p className="muted">
          اطلاعات روی سرور ذخیره می‌شود. برای اطمینان بیشتر، هر چند وقت یک‌بار فایل پشتیبان بگیرید.
        </p>
        <div className="row-actions">
          <button className="btn primary" onClick={exportData}>
            دانلود فایل پشتیبان
          </button>
          <button className="btn ghost" onClick={() => fileInput.current.click()}>
            بازیابی از فایل
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="application/json"
            hidden
            onChange={(e) => {
              if (e.target.files[0]) importData(e.target.files[0]);
              e.target.value = "";
            }}
          />
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>حذف صندوق</h2>
        </div>
        <button className="btn danger-btn" onClick={deleteFund}>
          حذف همیشگی این صندوق
        </button>
      </section>
    </div>
  );
}
