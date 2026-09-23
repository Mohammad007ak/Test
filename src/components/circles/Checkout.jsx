import { useEffect, useState } from "react";
import { CreditCard, FlaskConical, ShieldCheck } from "lucide-react";
import { Money, PageSkeleton, Spinner } from "../../ui/bits.jsx";
import { useToast } from "../../ui/feedback.jsx";
import { api } from "../../lib/api.js";
import { formatNumber } from "../../lib/format.js";
import { planById } from "../../lib/plans.js";

// Stands in for Digipay's payment page while the app runs on the simulator.
// With the live gateway the user is redirected to Digipay instead.
export default function Checkout({ checkoutId, done }) {
  const [checkout, setCheckout] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const toast = useToast();

  useEffect(() => {
    api("GET", `/api/checkouts/${checkoutId}`).then(setCheckout, setError);
  }, [checkoutId]);

  const finish = async (action) => {
    setBusy(action);
    try {
      const result = await api(
        "POST",
        `/api/checkouts/${checkoutId}/complete`,
        { action },
      );
      const message = !result.ok
        ? checkout.kind === "entry"
          ? "پرداخت لغو شد و عضویتی ثبت نشد"
          : "پرداخت لغو شد"
        : result.refunded
          ? "شما از قبل در این طرح عضو هستید؛ مبلغ برگردانده می‌شود"
          : checkout.kind === "entry"
            ? "قسط اول پرداخت شد و به صف گروه پیوستید"
            : "پرداخت با موفقیت انجام شد";
      toast(message, { tone: result.ok ? "success" : "error" });
      done(result.circleId);
    } catch (e) {
      toast(e.message, { tone: "error" });
      setBusy(null);
    }
  };

  if (error) return <p className="error-text home">{error.message}</p>;
  if (!checkout)
    return (
      <div className="home">
        <PageSkeleton />
      </div>
    );

  return (
    <div className="checkout-wrap">
      <div className="checkout">
        <div className="sim-flag">
          <FlaskConical size={14} /> درگاه آزمایشی؛ پولی جابه‌جا نمی‌شود
        </div>
        <div className="checkout-head">
          <CreditCard size={22} />
          <h1>
            {checkout.kind === "entry"
              ? "پرداخت قسط اول و عضویت"
              : "پرداخت سهم صندوق"}
          </h1>
        </div>
        <div className="checkout-amount">
          <span>مبلغ قابل پرداخت</span>
          <Money amount={checkout.amount} />
          <small>
            {checkout.kind === "entry"
              ? `قسط اول ${planById(checkout.planId)?.title ?? ""}`
              : `بابت ماه ${checkout.months.map((m) => formatNumber(m)).join("، ")}`}
          </small>
        </div>
        {checkout.status === "pending" ? (
          <div className="stack-sm">
            <button
              className="btn primary lg block"
              onClick={() => finish("pay")}
              disabled={Boolean(busy)}
            >
              {busy === "pay" ? <Spinner /> : "پرداخت"}
            </button>
            <button
              className="btn ghost block"
              onClick={() => finish("cancel")}
              disabled={Boolean(busy)}
            >
              انصراف
            </button>
          </div>
        ) : (
          <button
            className="btn outline block"
            onClick={() => done(checkout.circleId)}
          >
            {checkout.status === "cancelled"
              ? "لغو شده؛ بازگشت"
              : "پرداخت شده؛ بازگشت"}
          </button>
        )}
        <p className="fine-print">
          <ShieldCheck size={13} style={{ verticalAlign: "-2px" }} /> پرداخت امن
          از طریق دیجی‌پی
        </p>
      </div>
    </div>
  );
}
