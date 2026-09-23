import { useEffect, useState } from "react";
import { CreditCard, Hand, Repeat, ShieldCheck, Timer } from "lucide-react";
import Sheet from "../../ui/Sheet.jsx";
import { Money, Spinner } from "../../ui/bits.jsx";
import { api } from "../../lib/api.js";
import { randomHex } from "../../lib/fairness.js";
import { formatCompact, formatNumber } from "../../lib/format.js";

// One step: what the plan is, the terms (including the wallet-debit
// fallback), then the gateway to pay the first share. The seat is taken, and
// the waiting room opens, once that payment goes through. The credit check
// happens on the server before the gateway.
export default function JoinSheet({ plan, onClose, onCheckout }) {
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (plan) {
      setAccepted(false);
      setError(null);
    }
  }, [plan]);

  if (!plan) return <Sheet open={false} />;
  const pot = plan.size * plan.share;

  const join = async () => {
    setBusy(true);
    setError(null);
    try {
      const { checkoutId, redirectUrl } = await api(
        "POST",
        "/api/circles/join",
        {
          planId: plan.id,
          accept: true,
          // Randomness from this device, mixed into every draw of the circle.
          nonce: randomHex(16),
        },
      );
      if (redirectUrl) window.location.href = redirectUrl;
      else onCheckout(checkoutId);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={Boolean(plan)}
      onClose={onClose}
      title={plan.title}
      footer={
        <button
          className="btn primary lg"
          onClick={join}
          disabled={!accepted || busy}
        >
          {busy ? (
            <Spinner />
          ) : (
            `پرداخت قسط اول (${formatCompact(plan.share)} تومان) و پیوستن`
          )}
        </button>
      }
    >
      <div className="stack-sm">
        <div className="preview-card">
          <div>
            <span>مبلغی که یک‌جا دریافت می‌کنید</span>
            <Money amount={pot} />
          </div>
          <div>
            <span>سهم ماهانه</span>
            <Money amount={plan.share} />
          </div>
          <div>
            <span>مدت و اعضا</span>
            <strong>
              {formatNumber(plan.months)} ماه، {formatNumber(plan.size)} نفر
            </strong>
          </div>
        </div>

        <ul className="how-list">
          <li>
            <CreditCard size={18} />
            <span>
              برای گرفتن جایگاه، قسط اول ({formatCompact(plan.share)} تومان) را
              از درگاه پرداخت می‌کنید.
            </span>
          </li>
          <li>
            <Timer size={18} />
            <span>
              بعد از پرداخت، چند دقیقه صبر کنید تا گروه{" "}
              {formatNumber(plan.size)} نفره تکمیل شود.
            </span>
          </li>
          <li>
            <Repeat size={18} />
            <span>
              هر ماه همه سهمشان را می‌دهند و یک نفر کل {formatCompact(pot)}{" "}
              تومان را می‌گیرد.
            </span>
          </li>
          <li>
            <ShieldCheck size={18} />
            <span>
              دیجی‌پی مدیر و ضامن گروه است و پات ماه اول را برمی‌دارد.
            </span>
          </li>
          <li>
            <Hand size={18} />
            <span>
              از ماه دوم، دریافت‌کننده با قرعه‌ی قابل‌اثبات انتخاب می‌شود.
            </span>
          </li>
        </ul>

        <div className="terms">
          <strong>شرایط و قوانین</strong>
          <ul>
            <li>
              تا پایان دوره ({formatNumber(plan.months)} ماه) هر ماه{" "}
              {formatCompact(plan.share)} تومان سهم پرداخت می‌کنید؛ حتی بعد از
              دریافت پات.
            </li>
            <li>
              قسط اول هنگام عضویت پرداخت می‌شود و سهم ماه‌های بعد را هر ماه از
              درگاه پرداخت می‌کنید.
            </li>
            <li>
              اگر تا سررسید پرداخت نکنید، سهم همان ماه{" "}
              <b>به‌طور خودکار از کیف پول دیجی‌پی شما کسر می‌شود</b>.
            </li>
            <li>
              اگر موجودی کیف پول کافی نباشد، دیجی‌پی سهم را ضمانت می‌کند و تا
              تسویه در قرعه شرکت داده نمی‌شوید.
            </li>
            <li>پات ماه اول به دیجی‌پی به‌عنوان مدیر و ضامن گروه می‌رسد.</li>
            <li>
              اگر گروه در زمان مقرر تکمیل نشود یا پیش از شروع از صف خارج شوید،
              عضویت لغو و قسط اول <b>کامل به شما برگردانده می‌شود</b>.
            </li>
          </ul>
        </div>
        <label className="check-row">
          <input
            type="checkbox"
            checked={accepted}
            onChange={(e) => setAccepted(e.target.checked)}
          />
          <span>شرایط و قوانین را خواندم و می‌پذیرم.</span>
        </label>
        {error && <p className="error-text">{error}</p>}
      </div>
    </Sheet>
  );
}
