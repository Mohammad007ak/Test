import { useEffect, useState } from "react";
import { FlaskConical, LogOut } from "lucide-react";
import AppBar from "../../ui/AppBar.jsx";
import { PageSkeleton, Segmented } from "../../ui/bits.jsx";
import { api } from "../../lib/api.js";
import AdminLogin from "./AdminLogin.jsx";
import Dashboard from "./Dashboard.jsx";
import Circles from "./Circles.jsx";
import CircleDetail from "./CircleDetail.jsx";
import Debtors from "./Debtors.jsx";
import Events from "./Events.jsx";

const SECTIONS = [
  { value: "dashboard", label: "داشبورد", Component: Dashboard },
  { value: "circles", label: "دوره‌ها", Component: Circles },
  { value: "debtors", label: "بدهکاران", Component: Debtors },
  { value: "events", label: "رویدادها", Component: Events },
];

// The operator's admin panel: #/ops/<section>[/<circle id>].
export default function AdminPanel({ section, itemId, back, go, goBack }) {
  const current = SECTIONS.find((s) => s.value === section) ?? SECTIONS[0];
  // { configured, username, allowed } from the server; null while loading.
  const [auth, setAuth] = useState(null);

  useEffect(() => {
    api("GET", "/api/admin/me").then(setAuth, () => setAuth({ configured: false, allowed: false }));
  }, []);

  const logout = async () => {
    await api("POST", "/api/admin/logout").catch(() => {});
    setAuth((a) => ({ ...a, username: null, allowed: false }));
  };

  if (!auth) {
    return (
      <div className="home admin">
        <PageSkeleton />
      </div>
    );
  }
  if (!auth.allowed) {
    return (
      <div className="home admin">
        <AdminLogin
          configured={auth.configured}
          back={back}
          onLogin={(username) => setAuth({ configured: true, username, allowed: true })}
        />
      </div>
    );
  }

  if (current.value === "circles" && itemId) {
    return (
      <div className="home admin">
        <CircleDetail id={itemId} back={() => goBack("ops", "circles")} />
      </div>
    );
  }

  const { Component } = current;
  return (
    <div className="home admin">
      <AppBar
        onBack={back}
        title="پنل مدیریت طرح‌ها"
        sub={
          <>
            <FlaskConical size={13} /> داده‌های شبیه‌ساز دیجی‌پی
            {auth.username && <>، {auth.username}</>}
          </>
        }
      >
        {auth.username && (
          <button className="icon-btn" onClick={logout} aria-label="خروج مدیر" title="خروج مدیر">
            <LogOut size={20} />
          </button>
        )}
      </AppBar>
      <div className="page">
        <Segmented
          value={current.value}
          onChange={(v) => go("ops", v === "dashboard" ? undefined : v, undefined, { replace: true })}
          options={SECTIONS.map(({ value, label }) => ({ value, label }))}
        />
        <Component key={current.value} open={go} />
      </div>
    </div>
  );
}
