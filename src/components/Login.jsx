import { useEffect, useRef, useState } from "react";
import { ArrowRight, MessageSquareText, Phone, ShieldCheck } from "lucide-react";
import CoinCrowd from "../ui/CoinCrowd.jsx";
import OtpInput from "../ui/OtpInput.jsx";
import { Spinner } from "../ui/bits.jsx";
import { Logo } from "../ui/Logo.jsx";
import { api } from "../lib/api.js";
import { normalizePhone } from "../lib/phone.js";
import { toPersianDigits } from "../lib/jalali.js";

const RESEND_SECONDS = 60;

function formatPhone(phone) {
  return toPersianDigits(phone.replace(/^(\d{4})(\d{3})(\d{4})$/, "$1 $2 $3"));
}

export default function Login({ onLogin, onTour }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState("phone");
  const [devCode, setDevCode] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [countdown, setCountdown] = useState(0);
  // SMS autofill and the Enter key can both submit the same code; only the
  // first may go out, or the second fails because the code is already used.
  const verifying = useRef(false);

  useEffect(() => {
    if (countdown <= 0) return;
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  const normalized = normalizePhone(phone);

  const requestCode = async () => {
    if (!normalized) {
      setError("شماره موبایل را کامل وارد کنید؛ مثل ۰۹۱۲ ۱۲۳ ۴۵۶۷");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api("POST", "/api/auth/request-code", { phone: normalized });
      setDevCode(result.devCode ?? null);
      setCode("");
      setStep("code");
      setCountdown(RESEND_SECONDS);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const verify = async (value = code) => {
    if (value.length < 5 || verifying.current) return;
    verifying.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await api("POST", "/api/auth/verify", { phone: normalized, code: value });
      onLogin(result.phone);
    } catch (e) {
      setError(e.message);
      setCode("");
      setBusy(false);
      verifying.current = false;
    }
  };

  return (
    <div className="auth">
      <aside className="auth-art">
        <CoinCrowd
          title="قرض بی‌دردسر، شفاف و تضمینی"
          text="در طرح‌های تضمینی دیجی‌پی عضو شوید و یک‌جا وام بگیرید، یا صندوق خانوادگی‌تان را آنلاین مدیریت کنید."
        >
          <Logo light />
        </CoinCrowd>
      </aside>

      <main className="auth-panel">
        <form
          className="auth-card"
          onSubmit={(e) => {
            e.preventDefault();
            step === "phone" ? requestCode() : verify();
          }}
        >
          {step === "phone" ? (
            <>
              <header>
                <h2>ورود به دیجی قرض</h2>
                <p>شماره موبایلتان را وارد کنید تا کد ورود برایتان پیامک شود.</p>
              </header>
              <label className="field">
                <span>شماره موبایل</span>
                <div className="input big">
                  <Phone size={18} className="muted" />
                  <input
                    value={phone}
                    onChange={(e) => {
                      setPhone(e.target.value);
                      setError(null);
                    }}
                    inputMode="tel"
                    autoComplete="tel"
                    placeholder="۰۹۱۲ ۱۲۳ ۴۵۶۷"
                    dir="ltr"
                    autoFocus
                  />
                </div>
              </label>
              {error && <p className="error-text">{error}</p>}
              <button className="btn primary lg block" type="submit" disabled={busy || !phone}>
                {busy ? <Spinner /> : "دریافت کد ورود"}
              </button>
              <p className="fine-print">اگر حساب ندارید، با همین کار ساخته می‌شود.</p>
            </>
          ) : (
            <>
              <header>
                <button type="button" className="back-link" onClick={() => setStep("phone")}>
                  <ArrowRight size={16} /> تغییر شماره
                </button>
                <h2>کد تأیید را وارد کنید</h2>
                <p>
                  کد ۵ رقمی به <b dir="ltr">{formatPhone(normalized)}</b> پیامک شد.
                </p>
              </header>
              {devCode && (
                <div className="dev-code">
                  <MessageSquareText size={18} />
                  <span>حالت آزمایشی؛ پیامک واقعی ارسال نمی‌شود.</span>
                  <b dir="ltr">{toPersianDigits(devCode)}</b>
                </div>
              )}
              <OtpInput
                value={code}
                onChange={(v) => {
                  setCode(v);
                  setError(null);
                }}
                onComplete={verify}
                error={Boolean(error)}
                disabled={busy}
              />
              {error && <p className="error-text">{error}</p>}
              <button className="btn primary lg block" type="submit" disabled={busy || code.length < 5}>
                {busy ? <Spinner /> : "ورود"}
              </button>
              <p className="resend">
                {countdown > 0 ? (
                  <>ارسال دوباره تا {toPersianDigits(countdown)} ثانیه‌ی دیگر</>
                ) : (
                  <button type="button" className="link-btn" onClick={requestCode} disabled={busy}>
                    ارسال دوباره‌ی کد
                  </button>
                )}
              </p>
            </>
          )}
          <p className="fine-print">
            <ShieldCheck size={14} style={{ verticalAlign: "-2px" }} /> اطلاعات شما فقط برای اعضای صندوق خودتان قابل
            مشاهده است.
          </p>
          <nav className="auth-links" aria-label="درباره‌ی دیجی قرض">
            <a href="/welcome/">دیجی قرض چیست؟</a>
            <button type="button" className="link-btn" onClick={onTour}>
              راهنمای اپ
            </button>
            <a href="/welcome/#plans">طرح‌ها</a>
            <a href="/terms/">قوانین و حریم خصوصی</a>
          </nav>
        </form>
      </main>
    </div>
  );
}
