import { useEffect, useState } from "react";
import { ArrowRight, Eye, Lock, MessageSquareText, Phone, ShieldCheck, Sparkles } from "lucide-react";
import Pattern from "../ui/Pattern.jsx";
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

export default function Login({ onLogin }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState("phone");
  const [devCode, setDevCode] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [countdown, setCountdown] = useState(0);

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
    if (value.length < 5 || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api("POST", "/api/auth/verify", { phone: normalized, code: value });
      onLogin(result.phone);
    } catch (e) {
      setError(e.message);
      setCode("");
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <aside className="auth-art">
        <Pattern />
        <Logo light />
        <div>
          <h1>
            صندوق فامیلی‌تان، <em>شفاف</em> و بی‌دردسر
          </h1>
          <p className="lede">
            سهم‌های ماهانه، اقساط و قرعه‌کشی وام را یک‌جا مدیریت کنید؛ هر عضو هم وضعیت خودش را در گوشی می‌بیند.
          </p>
        </div>
        <ul className="value-props">
          <li>
            <span className="vp-icon">
              <Sparkles size={20} />
            </span>
            <div>
              <strong>قرعه‌کشی بی‌طرف</strong>
              <span>برنده را سرور انتخاب می‌کند و هر قرعه برای همه ثبت می‌شود.</span>
            </div>
          </li>
          <li>
            <span className="vp-icon">
              <Eye size={20} />
            </span>
            <div>
              <strong>همه در جریان‌اند</strong>
              <span>اعضا پرداخت‌ها، وام‌ها و موجودی صندوق را خودشان می‌بینند.</span>
            </div>
          </li>
          <li>
            <span className="vp-icon">
              <Lock size={20} />
            </span>
            <div>
              <strong>پول دست خودتان است</strong>
              <span>دیجی قرض فقط حساب‌وکتاب را نگه می‌دارد؛ پولی از اپ رد نمی‌شود.</span>
            </div>
          </li>
        </ul>
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
              <OtpInput value={code} onChange={setCode} onComplete={verify} error={Boolean(error)} />
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
            <ShieldCheck size={14} style={{ verticalAlign: "-2px" }} /> اطلاعات شما فقط برای اعضای صندوق خودتان قابل مشاهده است.
          </p>
        </form>
      </main>
    </div>
  );
}
