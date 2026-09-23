import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, Hand, Repeat, ShieldCheck, XCircle } from "lucide-react";
import Sheet from "../../ui/Sheet.jsx";
import { Money, Spinner } from "../../ui/bits.jsx";
import { api } from "../../lib/api.js";
import { randomHex } from "../../lib/fairness.js";
import { formatCompact, formatNumber } from "../../lib/format.js";

// Three steps: what you're signing up for → Digipay credit check → terms
// and payment method. The member's device supplies a random nonce that is
// mixed into every draw of the circle.
export default function JoinSheet({ plan, onClose, onJoined }) {
  const [step, setStep] = useState("intro");
  const [check, setCheck] = useState(null);
  const [payMethod, setPayMethod] = useState("auto");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (plan) {
      setStep("intro");
      setCheck(null);
      setAccepted(false);
      setError(null);
    }
  }, [plan]);

  if (!plan) return <Sheet open={false} />;
  const pot = plan.size * plan.share;

  const runCheck = async () => {
    setStep("check");
    setCheck(null);
    try {
      const result = await api("GET", "/api/eligibility");
      setCheck(result);
      if (result.approved && result.available >= plan.share) setTimeout(() => setStep("terms"), 900);
    } catch (e) {
      setCheck({ error: e.message });
    }
  };

  const join = async () => {
    setBusy(true);
    setError(null);
    try {
      const { circleId } = await api("POST", "/api/circles/join", {
        planId: plan.id,
        payMethod,
        accept: true,
        nonce: randomHex(16),
      });
      onJoined(circleId);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const rejected = check && !check.error && (!check.approved || check.available < plan.share);

  const footer =
    step === "intro" ? (
      <button className="btn primary" onClick={runCheck}>
        بررسی اعتبار و ادامه <ArrowLeft size={18} />
      </button>
    ) : step === "terms" ? (
      <button className="btn primary" onClick={join} disabled={!accepted || busy}>
        {busy ? <Spinner /> : "عضویت در طرح"}
      </button>
    ) : rejected || check?.error ? (
      <button className="btn outline" onClick={onClose}>
        بستن
      </button>
    ) : null;

  return (
    <Sheet open={Boolean(plan)} onClose={onClose} title={plan.title} footer={footer}>
      <div className="wizard-steps" aria-hidden="true">
        {["intro", "check", "terms"].map((s, i) => (
          <i key={s} className={["intro", "check", "terms"].indexOf(step) >= i ? "done" : ""} />
        ))}
      </div>

      {step === "intro" && (
        <div className="stack-sm">
          <div className="preview-card">
            <div>
              <span>سهم ماهانه‌ی شما</span>
              <Money amount={plan.share} />
            </div>
            <div>
              <span>مبلغی که یک بار دریافت می‌کنید</span>
              <Money amount={pot} />
            </div>
            <div>
              <span>مدت و اعضا</span>
              <strong>
                {formatNumber(plan.months)} ماه، {formatNumber(plan.size)} عضو
              </strong>
            </div>
          </div>
          <ul className="how-list">
            <li>
              <Repeat size={18} />
              <span>هر ماه همه‌ی اعضا سهمشان را می‌دهند و یک نفر کل پات ({formatCompact(pot)}) را دریافت می‌کند.</span>
            </li>
            <li>
              <ShieldCheck size={18} />
              <span>
                دیجی‌پی مدیر و ضامن صندوق است: پات ماه اول را برمی‌دارد، مثل بقیه سهمش را می‌دهد و اگر عضوی قسطش را ندهد،
                جایش پرداخت می‌کند.
              </span>
            </li>
            <li>
              <Hand size={18} />
              <span>
                از ماه دوم، دریافت‌کننده با قرعه‌کشی قابل‌اثبات انتخاب می‌شود؛ هر عضو می‌تواند درستی هر قرعه را خودش
                بررسی کند.
              </span>
            </li>
          </ul>
        </div>
      )}

      {step === "check" && (
        <div className="dialog-body" style={{ padding: "24px 0" }}>
          {!check ? (
            <>
              <Spinner />
              <h3>در حال بررسی اعتبار شما در دیجی‌پی…</h3>
            </>
          ) : check.error ? (
            <>
              <div className="d-icon danger">
                <XCircle size={26} />
              </div>
              <p>{check.error}</p>
            </>
          ) : rejected ? (
            <>
              <div className="d-icon danger">
                <XCircle size={26} />
              </div>
              <h3>{check.approved ? "سقف اعتبار شما برای این طرح کافی نیست" : "فعلاً امکان عضویت نیست"}</h3>
              <p>
                {check.approved
                  ? `اعتبار ماهانه‌ی باقی‌مانده‌ی شما ${formatCompact(check.available)} تومان است. طرح با سهم کمتر را امتحان کنید.`
                  : "بر اساس اعتبارسنجی دیجی‌پی، در حال حاضر عضویت در طرح‌های تضمینی برای شما فعال نیست."}
              </p>
            </>
          ) : (
            <>
              <div className="d-icon">
                <CheckCircle2 size={26} />
              </div>
              <h3>اعتبار شما تأیید شد</h3>
            </>
          )}
        </div>
      )}

      {step === "terms" && (
        <div className="stack-sm">
          <h3>روش پرداخت سهم ماهانه</h3>
          <div className="choice-list" role="radiogroup">
            <button
              type="button"
              role="radio"
              aria-checked={payMethod === "auto"}
              className={`choice ${payMethod === "auto" ? "on" : ""}`}
              onClick={() => setPayMethod("auto")}
            >
              <strong>برداشت خودکار از کیف پول</strong>
              <span>هر ماه در سررسید خودکار کم می‌شود؛ نه فراموشی، نه دیرکرد. پیشنهاد ما.</span>
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={payMethod === "manual"}
              className={`choice ${payMethod === "manual" ? "on" : ""}`}
              onClick={() => setPayMethod("manual")}
            >
              <strong>پرداخت دستی هر ماه</strong>
              <span>هر ماه یادآوری می‌گیرید و خودتان پرداخت می‌کنید.</span>
            </button>
          </div>

          <div className="terms">
            <strong>شرایط طرح</strong>
            <ul>
              <li>
                تا پایان دوره ({formatNumber(plan.months)} ماه) هر ماه {formatCompact(plan.share)} تومان می‌پردازید؛ حتی بعد از
                دریافت پات.
              </li>
              <li>دوره وقتی شروع می‌شود که ظرفیت ({formatNumber(plan.size)} نفر) پر شود.</li>
              <li>پات ماه اول به دیجی‌پی به‌عنوان مدیر و ضامن صندوق می‌رسد.</li>
              <li>عضوی که قسط معوق دارد تا تسویه در قرعه‌کشی شرکت داده نمی‌شود.</li>
            </ul>
          </div>
          <label className="check-row">
            <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} />
            <span>شرایط طرح را خواندم و می‌پذیرم.</span>
          </label>
          {error && <p className="error-text">{error}</p>}
        </div>
      )}
    </Sheet>
  );
}
