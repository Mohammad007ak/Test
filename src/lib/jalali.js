// Jalali (Persian calendar) helpers built on the browser's Intl support.
// Months are identified by keys like "1405-07" so they sort as plain strings.

export const MONTH_NAMES = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
];

// Pin to Iran time so the server and every browser agree on the current month.
const TIME_ZONE = "Asia/Tehran";

const partsFormatter = new Intl.DateTimeFormat("en-US-u-ca-persian-nu-latn", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "numeric",
  day: "numeric",
});

export function toJalali(date = new Date()) {
  const parts = Object.fromEntries(
    partsFormatter.formatToParts(date).map((p) => [p.type, p.value]),
  );
  return { year: Number(parts.year), month: Number(parts.month), day: Number(parts.day) };
}

export function makeMonthKey(year, month) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

export function parseMonthKey(key) {
  const [year, month] = key.split("-").map(Number);
  return { year, month };
}

export function currentMonthKey(date = new Date()) {
  const { year, month } = toJalali(date);
  return makeMonthKey(year, month);
}

export function addMonths(key, count) {
  const { year, month } = parseMonthKey(key);
  const index = year * 12 + (month - 1) + count;
  return makeMonthKey(Math.floor(index / 12), (index % 12) + 1);
}

export function monthsBetween(fromKey, toKey) {
  const months = [];
  for (let key = fromKey; key <= toKey; key = addMonths(key, 1)) months.push(key);
  return months;
}

export function toPersianDigits(value) {
  return String(value).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[d]);
}

export function monthLabel(key) {
  const { year, month } = parseMonthKey(key);
  return `${MONTH_NAMES[month - 1]} ${toPersianDigits(year)}`;
}

const dateFormatter = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "long",
  day: "numeric",
});

export function formatDate(isoString) {
  return dateFormatter.format(new Date(isoString));
}
