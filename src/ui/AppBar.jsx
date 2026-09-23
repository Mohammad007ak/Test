import { ArrowRight } from "lucide-react";

// The one top bar every inner screen uses: back, title, optional subtitle
// and actions. The home screen shows the logo instead of a back button.
export default function AppBar({ onBack, backLabel = "بازگشت", title, sub, children }) {
  return (
    <header className="appbar">
      {onBack && (
        <button className="icon-btn" onClick={onBack} aria-label={backLabel} title={backLabel}>
          <ArrowRight size={20} />
        </button>
      )}
      <div className="appbar-title">
        <h1>{title}</h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {children}
    </header>
  );
}
