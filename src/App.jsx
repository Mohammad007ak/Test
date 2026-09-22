import { useEffect, useState } from "react";
import Dashboard from "./components/Dashboard.jsx";
import Members from "./components/Members.jsx";
import Payments from "./components/Payments.jsx";
import Lottery from "./components/Lottery.jsx";
import Loans from "./components/Loans.jsx";
import Settings from "./components/Settings.jsx";
import Login from "./components/Login.jsx";
import FundList from "./components/FundList.jsx";
import MemberView from "./components/MemberView.jsx";
import { api } from "./lib/api.js";
import { useFundSync } from "./lib/useFundSync.js";
import { currentMonthKey, formatDate } from "./lib/jalali.js";

const TABS = [
  { id: "dashboard", label: "داشبورد", icon: "🏠", Component: Dashboard },
  { id: "payments", label: "پرداخت‌ها", icon: "💳", Component: Payments },
  { id: "lottery", label: "قرعه‌کشی", icon: "🎲", Component: Lottery },
  { id: "loans", label: "وام‌ها", icon: "📄", Component: Loans },
  { id: "members", label: "اعضا", icon: "👥", Component: Members },
  { id: "settings", label: "تنظیمات", icon: "⚙️", Component: Settings },
];

const SAVE_STATUS = {
  saving: "در حال ذخیره…",
  saved: "ذخیره شد ✓",
  error: "ذخیره نشد",
};

// Routes live in the URL hash (#/manage/<id>, #/view/<id>) so a refresh
// or a shared link lands on the same screen.
function parseRoute() {
  const [, page, id] = window.location.hash.split("/");
  return page === "manage" || page === "view" ? { page, id } : { page: "home" };
}

function useRoute() {
  const [route, setRoute] = useState(parseRoute);
  useEffect(() => {
    const onChange = () => setRoute(parseRoute());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const go = (page, id) => {
    window.location.hash = page === "home" ? "" : `/${page}/${id}`;
  };
  return [route, go];
}

function ManageFund({ fundId, go }) {
  const { state, status, error, update, flush, applyServer } = useFundSync(fundId);
  const [tab, setTab] = useState("dashboard");
  const currentMonth = currentMonthKey();

  if (error) {
    return (
      <div className="stack">
        <p className="danger">{error.message}</p>
        <button className="btn ghost" onClick={() => go("home")}>
          بازگشت به صندوق‌ها
        </button>
      </div>
    );
  }
  if (!state) return <p className="empty">در حال بارگذاری…</p>;

  const { Component } = TABS.find((t) => t.id === tab);

  return (
    <>
      <header className="topbar">
        <div>
          <h1>{state.fund.name}</h1>
          <span className="muted">
            {formatDate(new Date().toISOString())}،{" "}
            <span className={status === "error" ? "danger" : ""}>{SAVE_STATUS[status]}</span>
            {status === "error" && (
              <button className="link" onClick={flush}>
                تلاش دوباره
              </button>
            )}
          </span>
        </div>
        <div className="row-actions">
          <button className="btn ghost small" onClick={() => go("view", fundId)}>
            👁 نمای اعضا
          </button>
          <button className="btn ghost small" onClick={() => flush().then(() => go("home"))}>
            صندوق‌ها
          </button>
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
        update={update}
        currentMonth={currentMonth}
        goTo={setTab}
        goHome={() => go("home")}
        server={{ fundId, flush, applyServer }}
      />
    </>
  );
}

export default function App() {
  const [phone, setPhone] = useState(undefined);
  const [route, go] = useRoute();

  useEffect(() => {
    api("GET", "/api/me").then(
      (me) => setPhone(me.phone),
      () => setPhone(null),
    );
    const onLoggedOut = () => setPhone(null);
    window.addEventListener("sandogh:logged-out", onLoggedOut);
    return () => window.removeEventListener("sandogh:logged-out", onLoggedOut);
  }, []);

  const logout = async () => {
    await api("POST", "/api/auth/logout").catch(() => {});
    setPhone(null);
    go("home");
  };

  let content;
  if (phone === undefined) content = <p className="empty">در حال بارگذاری…</p>;
  else if (phone === null) content = <Login onLogin={setPhone} />;
  else if (route.page === "manage") content = <ManageFund key={route.id} fundId={route.id} go={go} />;
  else if (route.page === "view") content = <MemberView key={route.id} fundId={route.id} back={(isManager) => (isManager ? go("manage", route.id) : go("home"))} />;
  else content = <FundList phone={phone} open={go} onLogout={logout} />;

  return <main className="app">{content}</main>;
}
