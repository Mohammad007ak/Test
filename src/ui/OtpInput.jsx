import { useRef, useState } from "react";
import { toPersianDigits } from "../lib/jalali.js";

const toLatin = (s) =>
  s.replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d));

// One real input drawn as separate boxes. A single field is what phone
// keyboards, backspace, paste and SMS autofill all handle reliably; the
// boxes are only its picture.
export default function OtpInput({ length = 5, value, onChange, onComplete, error, disabled }) {
  const ref = useRef(null);
  const [focused, setFocused] = useState(false);

  const handleChange = (raw) => {
    const clean = toLatin(raw).replace(/\D/g, "").slice(0, length);
    if (clean === value) return;
    onChange(clean);
    if (clean.length === length) onComplete?.(clean);
  };

  const active = Math.min(value.length, length - 1);

  return (
    <div className={`otp ${error ? "error" : ""}`} dir="ltr" onClick={() => ref.current?.focus()}>
      <input
        ref={ref}
        className="otp-field"
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        inputMode="numeric"
        pattern="[0-9]*"
        autoComplete="one-time-code"
        maxLength={length * 2}
        aria-label={`کد تأیید ${length} رقمی`}
        disabled={disabled}
        autoFocus
      />
      {Array.from({ length }, (_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={`otp-box ${value[i] ? "filled" : ""} ${focused && i === active ? "active" : ""}`}
        >
          {value[i] ? toPersianDigits(value[i]) : ""}
        </span>
      ))}
    </div>
  );
}
