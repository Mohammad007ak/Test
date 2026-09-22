// Normalize Iranian mobile numbers to the 09xxxxxxxxx form so the same
// person matches whether they typed +98, 0098, or Persian digits.
export function normalizePhone(input) {
  const digits = String(input ?? "")
    .replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))
    .replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d))
    .replace(/\D/g, "");
  const local = digits.replace(/^(0098|98)(?=9\d{9}$)/, "").replace(/^(?=9\d{9}$)/, "0");
  return /^09\d{9}$/.test(local) ? local : null;
}
