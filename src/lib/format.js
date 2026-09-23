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

// "۳۰ میلیون" reads faster than "۳۰٬۰۰۰٬۰۰۰" in cards and captions.
export function formatCompact(amount) {
  const units = [
    [1e9, "میلیارد"],
    [1e6, "میلیون"],
    [1e3, "هزار"],
  ];
  for (const [size, label] of units) {
    if (Math.abs(amount) >= size) {
      const value = Math.round((amount / size) * 10) / 10;
      return `${value.toLocaleString("fa-IR")} ${label}`;
    }
  }
  return Math.round(amount).toLocaleString("fa-IR");
}

export function formatCard(number) {
  return toPersianDigits(
    String(number)
      .replace(/\D/g, "")
      .replace(/(\d{4})(?=\d)/g, "$1 "),
  );
}

export function reminderText(fund, memberName, amount) {
  const card = fund.cardNumber
    ? `\nشماره کارت: ${formatCard(fund.cardNumber)}${fund.cardHolder ? ` به نام ${fund.cardHolder}` : ""}`
    : "";
  return `سلام ${memberName} عزیز\nیادآوری ${fund.name}: مبلغ ${formatMoney(amount)} از پرداخت‌های شما مانده است.${card}\nممنون از همراهی‌تان 🌱`;
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
