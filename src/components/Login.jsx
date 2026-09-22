import { useState } from "react";
import { api } from "../lib/api.js";
import { normalizePhone } from "../lib/phone.js";
import { toPersianDigits } from "../lib/jalali.js";

export default function Login({ onLogin }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState("phone");
  const [devCode, setDevCode] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const requestCode = () =>
    run(async () => {
      if (!normalizePhone(phone)) throw new Error("شماره موبایل معتبر نیست. مثلاً ۰۹۱۲۱۲۳۴۵۶۷");
      const result = await api("POST", "/api/auth/request-code", { phone });
      setDevCode(result.devCode ?? null);
      setCode("");
      setStep("code");
    });

  const verify = () =>
    run(async () => {
      const result = await api("POST", "/api/auth/verify", { phone, code });
      onLogin(result.phone);
    });

  return (
    <div className="welcome">
      <div className="welcome-hero">
        <img src="/icon.svg" alt="" width="72" height="72" />
        <h1>صندوقچه</h1>
        <p>مدیریت ساده و شفاف صندوق قرض‌الحسنه‌ی خانوادگی و دوستانه</p>
        <ul className="features">
          <li>✓ ثبت سهم ماهانه و اقساط اعضا</li>
          <li>✓ قرعه‌کشی شفاف که همه‌ی اعضا می‌بینند</li>
          <li>✓ هر عضو وضعیت خودش را در گوشی می‌بیند</li>
          <li>✓ پول همیشه در حساب خود شما می‌ماند</li>
        </ul>
      </div>

      <section className="card narrow">
        <div className="card-head">
          <h2>{step === "phone" ? "ورود یا ثبت‌نام" : "کد تأیید"}</h2>
        </div>
        <form
          className="form"
          onSubmit={(e) => {
            e.preventDefault();
            step === "phone" ? requestCode() : verify();
          }}
        >
          {step === "phone" ? (
            <label>
              شماره موبایل
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                inputMode="tel"
                autoComplete="tel"
                placeholder="۰۹۱۲۱۲۳۴۵۶۷"
                dir="ltr"
                autoFocus
              />
            </label>
          ) : (
            <>
              <p className="muted">
                کد ۵ رقمی به {toPersianDigits(normalizePhone(phone))} پیامک شد.{" "}
                <button type="button" className="link" onClick={() => setStep("phone")}>
                  تغییر شماره
                </button>
              </p>
              {devCode && (
                <p className="notice">
                  حالت آزمایشی (سرویس پیامک وصل نیست): کد شما <b dir="ltr">{toPersianDigits(devCode)}</b>
                </p>
              )}
              <label>
                کد تأیید
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={5}
                  dir="ltr"
                  className="code-input"
                  autoFocus
                />
              </label>
            </>
          )}
          {error && <p className="danger">{error}</p>}
          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? "لطفاً صبر کنید…" : step === "phone" ? "دریافت کد" : "ورود"}
          </button>
          {step === "code" && (
            <button type="button" className="btn ghost" onClick={requestCode} disabled={busy}>
              ارسال دوباره‌ی کد
            </button>
          )}
        </form>
      </section>
    </div>
  );
}
