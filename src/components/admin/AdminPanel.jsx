import { FlaskConical } from "lucide-react";
import AppBar from "../../ui/AppBar.jsx";
import { Segmented } from "../../ui/bits.jsx";
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
          </>
        }
      />
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
