import { useRef } from "react";

const toLatin = (s) => s.replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d));

// Separate boxes that behave like one field: typing advances, backspace
// goes back, and pasting or SMS autofill spreads the whole code.
export default function OtpInput({ length = 5, value, onChange, onComplete, error }) {
  const refs = useRef([]);
  const digits = value.padEnd(length, " ").slice(0, length).split("");

  const set = (next) => {
    const clean = toLatin(next).replace(/\D/g, "").slice(0, length);
    onChange(clean);
    if (clean.length === length) onComplete?.(clean);
    return clean;
  };

  const handleInput = (index, raw) => {
    let typed = toLatin(raw).replace(/\D/g, "");
    if (!typed) return;
    // Typing into a filled box without selecting it yields old+new digits.
    if (typed.length === 2 && value[index]) typed = typed[0] === value[index] ? typed[1] : typed[0];
    if (typed.length > 1) {
      const clean = set(typed);
      refs.current[Math.min(clean.length, length - 1)]?.focus();
      return;
    }
    const chars = value.split("");
    chars[index] = typed;
    set(chars.join(""));
    refs.current[Math.min(index + 1, length - 1)]?.focus();
  };

  const handleKey = (index, e) => {
    if (e.key === "Backspace") {
      e.preventDefault();
      if (value[index]) {
        set(value.slice(0, index) + value.slice(index + 1));
      } else if (index > 0) {
        set(value.slice(0, index - 1) + value.slice(index));
        refs.current[index - 1]?.focus();
      }
    } else if (e.key === "ArrowLeft") {
      refs.current[Math.min(index + 1, length - 1)]?.focus();
    } else if (e.key === "ArrowRight") {
      refs.current[Math.max(index - 1, 0)]?.focus();
    }
  };

  return (
    <div className={`otp ${error ? "error" : ""}`} dir="ltr">
      {digits.map((d, i) => (
        <input
          key={i}
          ref={(el) => (refs.current[i] = el)}
          value={d.trim()}
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          aria-label={`رقم ${i + 1}`}
          className={d.trim() ? "filled" : ""}
          onChange={(e) => handleInput(i, e.target.value)}
          onKeyDown={(e) => handleKey(i, e)}
          onFocus={(e) => {
            // Keep the code contiguous: jump to the first empty box.
            if (i > value.length) refs.current[value.length]?.focus();
            else e.target.select();
          }}
          onPaste={(e) => {
            e.preventDefault();
            const clean = set(e.clipboardData.getData("text"));
            refs.current[Math.min(clean.length, length - 1)]?.focus();
          }}
          autoFocus={i === 0}
        />
      ))}
    </div>
  );
}
