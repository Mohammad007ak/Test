import { createContext, useCallback, useContext, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import Sheet from "./Sheet.jsx";

const FeedbackContext = createContext(null);

export function useToast() {
  return useContext(FeedbackContext).toast;
}

export function useDialog() {
  return useContext(FeedbackContext).confirm;
}

const DIALOG_ICONS = { danger: AlertTriangle, gold: Info, brand: Info };

// Toasts replace alert(); confirm() returns a promise and replaces
// window.confirm/prompt with an on-brand dialog (optionally type-to-confirm).
export function FeedbackProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const [dialog, setDialog] = useState(null);
  const [typed, setTyped] = useState("");
  const seq = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((all) => all.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
    setTimeout(() => setToasts((all) => all.filter((t) => t.id !== id)), 200);
  }, []);

  const toast = useCallback(
    (message, { tone = "success", action, duration = 3500 } = {}) => {
      const id = ++seq.current;
      setToasts((all) => [...all.slice(-2), { id, message, tone, action }]);
      setTimeout(() => dismiss(id), duration);
    },
    [dismiss],
  );

  const confirm = useCallback(
    (options) =>
      new Promise((resolve) => {
        setTyped("");
        setDialog({ tone: "brand", confirmLabel: "تأیید", cancelLabel: "انصراف", ...options, resolve });
      }),
    [],
  );

  const close = (result) => {
    dialog?.resolve(result);
    setDialog((d) => (d ? { ...d, open: false } : d));
  };

  const Icon = DIALOG_ICONS[dialog?.tone] ?? Info;
  const blocked = dialog?.requireText && typed.trim() !== dialog.requireText;

  return (
    <FeedbackContext.Provider value={{ toast, confirm }}>
      {children}
      <Sheet
        open={Boolean(dialog && dialog.open !== false)}
        onClose={() => close(false)}
        narrow
        footer={
          dialog && (
            <>
              <button className="btn outline" onClick={() => close(false)}>
                {dialog.cancelLabel}
              </button>
              <button
                className={`btn ${dialog.tone === "danger" ? "danger solid" : "primary"}`}
                onClick={() => close(true)}
                disabled={blocked}
              >
                {dialog.confirmLabel}
              </button>
            </>
          )
        }
      >
        {dialog && (
          <div className="dialog-body">
            <div className={`d-icon ${dialog.tone}`}>
              <Icon size={26} />
            </div>
            <h2>{dialog.title}</h2>
            {dialog.body && <p>{dialog.body}</p>}
            {dialog.requireText && (
              <label className="input">
                <input
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  placeholder={dialog.requireText}
                  aria-label={`برای تأیید بنویسید: ${dialog.requireText}`}
                  autoFocus
                />
              </label>
            )}
          </div>
        )}
      </Sheet>
      {createPortal(
        <div className="toasts" role="status" aria-live="polite">
          {toasts.map((t) => (
            <div key={t.id} className={`toast ${t.tone} ${t.leaving ? "leaving" : ""}`}>
              <span className="t-icon">{t.tone === "error" ? <XCircle size={18} /> : <CheckCircle2 size={18} />}</span>
              <span>{t.message}</span>
              {t.action && (
                <button
                  onClick={() => {
                    t.action.onClick();
                    dismiss(t.id);
                  }}
                >
                  {t.action.label}
                </button>
              )}
            </div>
          ))}
        </div>,
        document.body,
      )}
    </FeedbackContext.Provider>
  );
}
