// The guaranteed plans. Position 1 in every circle is the operator
// (Digipay): it pays its share like everyone else and always takes month 1.
// A retired plan is no longer offered, but circles already running on it
// keep working until they finish.
export const PLANS = [
  { id: "p6-5", title: "طرح شش‌ماهه", size: 6, months: 6, share: 5_000_000, flag: "تازه" },
  { id: "p6-10", title: "طرح شش‌ماهه‌ی ویژه", size: 6, months: 6, share: 10_000_000 },
  { id: "p12-5", title: "طرح یک‌ساله", size: 12, months: 12, share: 5_000_000, flag: "پرطرفدار" },
  { id: "p12-10", title: "طرح یک‌ساله‌ی ویژه", size: 12, months: 12, share: 10_000_000 },
  { id: "p24-10", title: "طرح دوساله", size: 24, months: 24, share: 10_000_000, retired: true },
];

export const OFFERED_PLANS = PLANS.filter((p) => !p.retired);

export function planById(id) {
  return PLANS.find((p) => p.id === id) ?? null;
}

export function potOf(plan) {
  return plan.size * plan.share;
}
