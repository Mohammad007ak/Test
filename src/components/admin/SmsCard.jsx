import { useEffect, useState } from "react";
import { MessageSquareText, Send } from "lucide-react";
import { Spinner } from "../../ui/bits.jsx";
import { api } from "../../lib/api.js";
import { formatNumber } from "../../lib/format.js";
import { toPersianDigits } from "../../lib/jalali.js";

const PROVIDER = { "sms.ir": "SMS.ir", kavenegar: "کاوه‌نگار" };

// Is login-by-SMS really working? Shows the provider's own answer (credit,
// or the exact error) and sends a test code to a number.
export default function SmsCard() {
  const [status, setStatus] = useState(null);
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    api("GET", "/api/ops/sms").then(setStatus, (e) => setStatus({ error: e.message }));
  }, []);

  const test = async (e) => {
    e.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      setResult(await api("POST", "/api/ops/sms/test", { phone }));
    } catch (err) {
      setResult({ ok: false, error: err.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <div className="section-title">
        <h2>
          <MessageSquareText size={17} /> سرویس پیامک ورود
        </h2>
        {status?.configured &&
          (status.sandbox ? (
            <span className="badge gold">Sandbox؛ پیامک واقعی ارسال نمی‌شود</span>
          ) : status.error ? (
            <span className="badge danger">خطا</span>
          ) : (
            <span className="badge success">فعال</span>
          ))}
      </div>

      {!status ? (
        <Spinner />
      ) : !status.configured ? (
        <p className="muted small">
          هیچ سرویس پیامکی تنظیم نشده؛ کد ورود روی صفحه نمایش داده می‌شود. برای ارسال واقعی، متغیرهای SMSIR_API_KEY و
          SMSIR_TEMPLATE_ID را تنظیم کنید.
        </p>
      ) : (
        <div className="stack-sm">
          <div className="admin-stats">
            <div>
              <span>سرویس</span>
              <strong>{PROVIDER[status.provider] ?? status.provider}</strong>
            </div>
            {status.templateId !== undefined && (
              <div>
                <span>شناسه‌ی قالب</span>
                <strong>{toPersianDigits(status.templateId)}</strong>
              </div>
            )}
            {status.credit !== undefined && !Number.isNaN(status.credit) && (
              <div>
                <span>اعتبار باقی‌مانده</span>
                <strong>{formatNumber(Math.floor(status.credit))}</strong>
              </div>
            )}
          </div>
          {status.error && (
            <p className="error-text" dir="auto">
              پاسخ سرویس پیامک: {status.error}
            </p>
          )}
          <form className="sms-test" onSubmit={test}>
            <div className="input sm">
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                inputMode="tel"
                placeholder="۰۹۱۲ ۱۲۳ ۴۵۶۷"
                dir="ltr"
                aria-label="شماره برای پیامک آزمایشی"
              />
            </div>
            <button className="btn sm primary" disabled={busy || !phone}>
              {busy ? <Spinner /> : <Send size={15} />} ارسال پیامک آزمایشی
            </button>
          </form>
          {result &&
            (result.ok ? (
              <p className="verify ok">
                {result.sandbox
                  ? `درخواست پذیرفته شد (Sandbox، پیامکی ارسال نمی‌شود). کد: ${toPersianDigits(result.code)}`
                  : `ارسال شد. کد ${toPersianDigits(result.code)} باید به گوشی برسد.`}
              </p>
            ) : (
              <p className="error-text" dir="auto">
                ارسال نشد: {result.error}
              </p>
            ))}
        </div>
      )}
    </section>
  );
}
