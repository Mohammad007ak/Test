import { toPersianDigits } from "./jalali.js";

export function formatMoney(amount) {
  return `${Math.round(amount).toLocaleString("fa-IR")} تومان`;
}

export function formatNumber(value) {
  return toPersianDigits(value);
}

// Accept Persian, Arabic or Latin digits and ignore separators.
export function parseAmount(text) {
  const latin = String(text)
    .replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))
    .replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d))
    .replace(/[^\d]/g, "");
  return latin ? Number(latin) : 0;
}

export function reminderText(fundName, memberName, amount) {
  return `سلام ${memberName} عزیز، یادآوری ${fundName}: مبلغ ${formatMoney(amount)} از پرداخت‌های شما معوق است. لطفاً در اولین فرصت واریز کنید. ممنون 🙏`;
}

export function smsLink(phone, text) {
  return `sms:${phone}?&body=${encodeURIComponent(text)}`;
}

// The clipboard API needs a secure context, which a phone on the local
// network (http://192.168…) is not; fall back to a prompt the user can copy from.
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    window.prompt("متن را کپی کنید:", text);
    return false;
  }
}
