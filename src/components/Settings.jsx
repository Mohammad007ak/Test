import { useRef } from "react";
import FundForm from "./FundForm.jsx";
import { createEmptyState } from "../lib/fund.js";
import { isValidState } from "../lib/storage.js";

export default function Settings({ state, update, replace }) {
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
      if (confirm("اطلاعات فعلی با فایل پشتیبان جایگزین شود؟")) replace(data);
    } catch {
      alert("فایل پشتیبان معتبر نیست.");
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
          اطلاعات فقط روی همین مرورگر ذخیره می‌شود. هر چند وقت یک‌بار فایل پشتیبان بگیرید.
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
          <h2>پاک کردن همه‌چیز</h2>
        </div>
        <button
          className="btn danger-btn"
          onClick={() => confirm("همه‌ی اطلاعات صندوق پاک شود؟ این کار برگشت‌پذیر نیست.") && replace(createEmptyState())}
        >
          پاک کردن اطلاعات
        </button>
      </section>
    </div>
  );
}
