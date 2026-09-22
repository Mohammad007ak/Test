import { useEffect, useState } from "react";
import Dashboard from "./components/Dashboard.jsx";
import Members from "./components/Members.jsx";
import Payments from "./components/Payments.jsx";
import Lottery from "./components/Lottery.jsx";
import Loans from "./components/Loans.jsx";
import Settings from "./components/Settings.jsx";
import FundForm from "./components/FundForm.jsx";
import { loadState, saveState } from "./lib/storage.js";
import { createDemoState } from "./lib/demo.js";
import { currentMonthKey, formatDate } from "./lib/jalali.js";

const TABS = [
  { id: "dashboard", label: "داشبورد", icon: "🏠", Component: Dashboard },
  { id: "payments", label: "پرداخت‌ها", icon: "💳", Component: Payments },
  { id: "lottery", label: "قرعه‌کشی", icon: "🎲", Component: Lottery },
  { id: "loans", label: "وام‌ها", icon: "📄", Component: Loans },
  { id: "members", label: "اعضا", icon: "👥", Component: Members },
  { id: "settings", label: "تنظیمات", icon: "⚙️", Component: Settings },
];

function Welcome({ onCreate, onDemo }) {
  return (
    <div className="welcome">
      <div className="welcome-hero">
        <img src="/icon.svg" alt="" width="72" height="72" />
        <h1>صندوقچه</h1>
        <p>مدیریت ساده و شفاف صندوق قرض‌الحسنه‌ی خانوادگی و دوستانه</p>
        <ul className="features">
          <li>✓ ثبت سهم ماهانه و اقساط اعضا</li>
          <li>✓ قرعه‌کشی شفاف وام</li>
          <li>✓ یادآوری پیامکی به بدهکارها</li>
          <li>✓ پول همیشه در حساب خود شما می‌ماند</li>
        </ul>
        <button className="btn ghost" onClick={onDemo}>
          دیدن نمونه با اطلاعات آزمایشی
        </button>
      </div>
      <section className="card">
        <div className="card-head">
          <h2>ساخت صندوق جدید</h2>
        </div>
        <FundForm onSave={onCreate} submitLabel="ساخت صندوق" />
      </section>
    </div>
  );
}

export default function App() {
  const [state, setState] = useState(loadState);
  const [tab, setTab] = useState("dashboard");
  const currentMonth = currentMonthKey();

  useEffect(() => saveState(state), [state]);

  if (!state.fund) {
    return (
      <main className="app">
        <Welcome
          onCreate={(fund) => setState((s) => ({ ...s, fund }))}
          onDemo={() => setState(createDemoState())}
        />
      </main>
    );
  }

  const { Component } = TABS.find((t) => t.id === tab);

  return (
    <main className="app">
      <header className="topbar">
        <div>
          <h1>{state.fund.name}</h1>
          <span className="muted">{formatDate(new Date().toISOString())}</span>
        </div>
      </header>
      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={t.id === tab ? "active" : ""} onClick={() => setTab(t.id)}>
            <span aria-hidden>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>
      <Component
        key={tab}
        state={state}
        update={setState}
        replace={(next) => {
          setState(next);
          setTab("dashboard");
        }}
        currentMonth={currentMonth}
        goTo={setTab}
      />
    </main>
  );
}
