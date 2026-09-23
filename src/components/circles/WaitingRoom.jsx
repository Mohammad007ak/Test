import { useEffect, useState } from "react";
import { LogOut, TimerOff, Users } from "lucide-react";
import { LogoMark } from "../../ui/Logo.jsx";
import { Spinner } from "../../ui/bits.jsx";
import { useDialog, useToast } from "../../ui/feedback.jsx";
import { api } from "../../lib/api.js";
import { formatCompact, formatNumber } from "../../lib/format.js";
import { toPersianDigits } from "../../lib/jalali.js";

function useCountdown(deadline) {
  const [left, setLeft] = useState(() => Math.max(0, deadline - Date.now()));
  useEffect(() => {
    const t = setInterval(() => setLeft(Math.max(0, deadline - Date.now())), 1000);
    return () => clearInterval(t);
  }, [deadline]);
  return left;
}

function clock(ms) {
  const total = Math.ceil(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return toPersianDigits(`${m}:${String(s).padStart(2, "0")}`);
}

// Shown while a circle is filling up. The parent polls the circle, so the
// seats light up as people join and the page moves on once it's full.
export default function WaitingRoom({ view, ops, onLeft, onRetry, reload }) {
  const { circle, members } = view;
  const left = useCountdown(circle.deadline);
  const [busy, setBusy] = useState(null);
  const confirm = useDialog();
  const toast = useToast();

  if (circle.status === "expired") {
    return (
      <section className="waiting expired">
        <div className="waiting-orb">
          <TimerOff size={40} />
        </div>
        <h2>گروه در زمان مقرر تکمیل نشد</h2>
        <p>عضویت شما لغو شد و قسط اولی که پرداخت کرده بودید به شما برگردانده می‌شود. می‌توانید دوباره امتحان کنید.</p>
        <button className="btn primary lg" onClick={onRetry}>
          تلاش دوباره
        </button>
      </section>
    );
  }

  const leave = async () => {
    const ok = await confirm({
      title: "خروج از صف؟",
      body: "جای شما در این گروه آزاد می‌شود و قسط اول به شما برگردانده می‌شود.",
      confirmLabel: "خروج از صف",
      tone: "danger",
    });
    if (!ok) return;
    setBusy("leave");
    try {
      await api("POST", `/api/circles/${circle.id}/leave`);
      toast("از صف خارج شدید؛ قسط اول برگردانده می‌شود");
      onLeft();
    } catch (e) {
      toast(e.message, { tone: "error" });
      setBusy(null);
    }
  };

  const fill = async () => {
    setBusy("fill");
    try {
      await api("POST", `/api/ops/circles/${circle.id}/fill`);
      await reload();
    } catch (e) {
      toast(e.message, { tone: "error" });
    } finally {
      setBusy(null);
    }
  };

  const seats = Array.from({ length: circle.size }, (_, i) => members[i] ?? null);

  return (
    <section className="waiting">
      <div className="waiting-orb" aria-hidden="true">
        <span className="pulse" />
        <span className="pulse delay" />
        <Users size={40} />
      </div>
      <h2>در حال تکمیل گروه شما…</h2>
      <p>
        {formatNumber(circle.taken)} نفر از {formatNumber(circle.size)} نفر آماده‌اند. به محض تکمیل، دوره شروع می‌شود و
        خبرتان می‌کنیم.
      </p>

      <div className="waiting-seats" aria-label={`${circle.taken} از ${circle.size} جا پر شده`}>
        {seats.map((m, i) => (
          <span key={i} className={`wseat ${m ? "on" : ""} ${m?.isMe ? "me" : ""} ${m?.isOperator ? "op" : ""}`}>
            {m?.isOperator ? <LogoMark size={20} /> : m?.isMe ? "شما" : m ? toPersianDigits(m.position) : ""}
          </span>
        ))}
      </div>

      <div className="waiting-stats">
        <div>
          <span>زمان باقی‌مانده</span>
          <strong dir="ltr">{clock(left)}</strong>
        </div>
        <div>
          <span>دریافت یک‌جا</span>
          <strong>{formatCompact(circle.pot)}</strong>
        </div>
        <div>
          <span>سهم ماهانه</span>
          <strong>{formatCompact(circle.share)}</strong>
        </div>
      </div>

      <p className="small muted">معمولاً کمتر از ۵ دقیقه طول می‌کشد. می‌توانید از اپ خارج شوید؛ جای شما محفوظ است.</p>

      <div className="waiting-actions">
        <button className="btn ghost" onClick={leave} disabled={Boolean(busy)}>
          {busy === "leave" ? <Spinner /> : <LogOut size={17} />} خروج از صف
        </button>
        {ops && (
          <button className="btn outline" onClick={fill} disabled={Boolean(busy)}>
            {busy === "fill" ? <Spinner /> : <Users size={17} />} تکمیل آزمایشی
          </button>
        )}
      </div>
    </section>
  );
}
