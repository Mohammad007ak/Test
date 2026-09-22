import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

// Bottom sheet on phones, centered dialog on wider screens.
export default function Sheet({ open, onClose, title, children, footer, narrow = false, dismissible = true }) {
  const [mounted, setMounted] = useState(open);
  const [closing, setClosing] = useState(false);
  const panel = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (open) {
      setMounted(true);
      setClosing(false);
    } else if (mounted) {
      setClosing(true);
      const t = setTimeout(() => setMounted(false), 200);
      return () => clearTimeout(t);
    }
  }, [open, mounted]);

  useEffect(() => {
    if (!mounted || closing) return;
    const previous = document.activeElement;
    const focusable = panel.current?.querySelector("[autofocus], input, select, button:not(.icon-btn)");
    focusable?.focus({ preventScroll: true });
    const onKey = (e) => e.key === "Escape" && dismissible && onCloseRef.current?.();
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      previous?.focus?.({ preventScroll: true });
    };
  }, [mounted, closing, dismissible]);

  if (!mounted) return null;

  return createPortal(
    <div
      className={`overlay ${closing ? "closing" : ""}`}
      onMouseDown={(e) => e.target === e.currentTarget && dismissible && onClose?.()}
    >
      <div className={`sheet ${narrow ? "narrow" : ""}`} role="dialog" aria-modal="true" aria-label={title} ref={panel}>
        <div className="sheet-grip" />
        {title && (
          <div className="sheet-head">
            <h2>{title}</h2>
            {dismissible && (
              <button className="icon-btn sm soft" onClick={onClose} aria-label="بستن">
                <X size={18} />
              </button>
            )}
          </div>
        )}
        <div className="sheet-body">{children}</div>
        {footer && <div className="sheet-foot">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
