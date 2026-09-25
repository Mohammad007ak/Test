import { planById } from "../../lib/plans.js";
import { formatCompact, formatNumber } from "../../lib/format.js";
import { formatDay, toPersianDigits } from "../../lib/jalali.js";

export const STATUS = {
  forming: { label: "در حال تکمیل", badge: "gold" },
  active: { label: "فعال", badge: "brand" },
  completed: { label: "پایان‌یافته", badge: "success" },
  expired: { label: "منقضی", badge: "" },
};

export function StatusBadge({ status }) {
  const s = STATUS[status] ?? { label: status, badge: "" };
  return <span className={`badge ${s.badge}`}>{s.label}</span>;
}

// Where an installment came from, in the words the operator uses.
export const METHOD = {
  entry: "هنگام عضویت",
  manual: "درگاه",
  wallet: "کیف پول",
  guarantee: "ضمانت دیجی‌پی",
  operator: "سهم دیجی‌پی",
};

export const planTitle = (planId) => planById(planId)?.title ?? planId;

const timeFormatter = new Intl.DateTimeFormat("fa-IR", {
  timeZone: "Asia/Tehran",
  hour: "2-digit",
  minute: "2-digit",
});

// "۱۵ مهر، ۱۴:۳۰"
export const formatWhen = (t) => (t ? `${formatDay(t)}، ${timeFormatter.format(new Date(t))}` : "—");

// "۳ دقیقه و ۱۰ ثانیه", "۲ ساعت و ۵ دقیقه"
export function formatDuration(ms) {
  if (ms === null || ms === undefined) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${formatNumber(s)} ثانیه`;
  const m = Math.floor(s / 60);
  if (m < 60) return s % 60 ? `${formatNumber(m)} دقیقه و ${formatNumber(s % 60)} ثانیه` : `${formatNumber(m)} دقیقه`;
  const h = Math.floor(m / 60);
  if (h < 48) return m % 60 ? `${formatNumber(h)} ساعت و ${formatNumber(m % 60)} دقیقه` : `${formatNumber(h)} ساعت`;
  return `${formatNumber(Math.floor(h / 24))} روز`;
}

export const toman = (amount) => `${formatCompact(amount)} تومان`;
export const seat = (position) => (position ? `جایگاه ${toPersianDigits(position)}` : "");

// One line per audit event.
export function describeEvent(e) {
  const d = e.detail ?? {};
  switch (e.kind) {
    case "circle_created":
      return "گروه جدید ساخته شد";
    case "circle_started":
      return `گروه تکمیل و دوره شروع شد (در ${formatDuration(d.fillMs)})`;
    case "circle_expired":
      return `گروه در مهلت تکمیل نشد (${formatNumber(d.taken)} از ${formatNumber(d.size)} نفر)`;
    case "joined":
      return `عضو جدید در جایگاه ${toPersianDigits(d.position)}؛ قسط اول پرداخت شد`;
    case "left":
      return "خروج از صف پیش از شروع";
    case "refund":
      return d.reason === "expired"
        ? "بازگشت قسط اول (گروه منقضی شد)"
        : d.reason === "duplicate"
          ? "بازگشت پرداخت تکراری"
          : "بازگشت قسط اول (خروج از صف)";
    case "gateway_payment":
      return "پرداخت قسط از درگاه";
    case "wallet_debit":
      return `کسر خودکار قسط ماه ${formatNumber(d.month)} از کیف پول`;
    case "wallet_failed":
      return `کسر از کیف پول ناموفق (ماه ${formatNumber(d.month)})`;
    case "guarantee":
      return `قسط ماه ${formatNumber(d.month)} با ضمانت دیجی‌پی پرداخت شد`;
    case "debt_settled":
      return "بدهی تسویه شد";
    case "late_fee":
      return "جریمه‌ی تأخیر دریافت شد";
    case "held":
      return `ماه ${formatNumber(d.month)}: همه‌ی ${formatNumber(d.owing)} نفر باقی‌مانده بدهکارند؛ مبلغ نزد دیجی‌پی امانت ماند`;
    case "held_claimed":
      return `مبلغ امانت ماه ${formatNumber(d.month)} پس از تسویه به جایگاه ${toPersianDigits(d.position)} رسید`;
    case "forfeit":
      return `مبلغ امانت ماه ${formatNumber(d.month)} پس از پایان مهلت به دیجی‌پی رسید`;
    case "debt_forfeited":
      return "بدهی با وام سوخته‌ی عضو تسویه شد";
    case "draw":
      return d.kind === "operator"
        ? `ماه ${formatNumber(d.month)}: سهم دیجی‌پی`
        : d.kind === "last"
          ? `ماه ${formatNumber(d.month)}: آخرین نفر، جایگاه ${toPersianDigits(d.position)}`
          : `قرعه‌ی ماه ${formatNumber(d.month)} بین ${formatNumber(d.eligible)} نفر: جایگاه ${toPersianDigits(d.position)}`;
    case "payout":
      return `واریز مبلغ ماه ${formatNumber(d.month)} ${d.operator ? "به دیجی‌پی" : "به برنده"}`;
    default:
      return e.kind;
  }
}

export const EVENT_KINDS = [
  ["joined", "عضویت"],
  ["gateway_payment", "پرداخت درگاه"],
  ["wallet_debit", "کسر از کیف پول"],
  ["wallet_failed", "کسر ناموفق"],
  ["guarantee", "ضمانت"],
  ["debt_settled", "تسویه‌ی بدهی"],
  ["late_fee", "جریمه‌ی تأخیر"],
  ["held", "امانت"],
  ["held_claimed", "دریافت امانت"],
  ["forfeit", "سوخت امانت"],
  ["draw", "قرعه"],
  ["payout", "واریز"],
  ["refund", "بازگشت وجه"],
  ["circle_started", "شروع دوره"],
  ["circle_expired", "انقضای گروه"],
];

// Events that are money leaving Digipay's pocket or needing attention.
export const eventTone = (kind) =>
  ({
    wallet_failed: "danger",
    guarantee: "danger",
    refund: "gold",
    circle_expired: "gold",
    held: "gold",
    forfeit: "gold",
    late_fee: "brand",
    payout: "brand",
    draw: "brand",
  })[kind] ?? "";
