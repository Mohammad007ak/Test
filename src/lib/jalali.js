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
  const parts = Object.fromEntries(partsFormatter.formatToParts(date).map((p) => [p.type, p.value]));
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

const DAY = 24 * 60 * 60 * 1000;
const monthIndex = ({ year, month }) => year * 12 + month - 1;

// The same moment `count` Jalali months later, on the same day of the month
// (or the month's last day, when it's shorter). Iran has no daylight saving
// time, so stepping whole days keeps the time of day.
export function addJalaliMonths(timestamp, count) {
  const start = toJalali(new Date(timestamp));
  const target = monthIndex(start) + count;
  let t = timestamp + Math.round(count * 30.44) * DAY;
  for (let i = 0; i < 40; i++) {
    const current = monthIndex(toJalali(new Date(t)));
    if (current === target) break;
    t += (current < target ? 1 : -1) * DAY;
  }
  for (let i = 0; i < 40; i++) {
    const { day } = toJalali(new Date(t));
    if (day === start.day) break;
    if (day > start.day) t -= DAY;
    else if (monthIndex(toJalali(new Date(t + DAY))) !== target)
      break; // month ended first
    else t += DAY;
  }
  return t;
}

// "۱۵ مهر"
export function formatDay(timestamp) {
  const { month, day } = toJalali(new Date(timestamp));
  return `${toPersianDigits(day)} ${MONTH_NAMES[month - 1]}`;
}
