import { useState } from "react";
import { KeyRound, Lock, User } from "lucide-react";
import AppBar from "../../ui/AppBar.jsx";
import { Spinner } from "../../ui/bits.jsx";
import { api } from "../../lib/api.js";

// Username/password sign-in for the admin panel.
export default function AdminLogin({ configured, onLogin, back }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api("POST", "/api/admin/login", { username, password });
      onLogin(r.username);
    } catch (err) {
      setError(err.message);
      setPassword("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <AppBar onBack={back} title="پنل مدیریت" />
      <form className="auth-card admin-login" onSubmit={submit}>
        <header>
          <span className="admin-login-icon">
            <KeyRound size={26} />
          </span>
          <h2>ورود مدیر</h2>
          <p>
            {configured
              ? "با نام کاربری و رمز عبور مدیر وارد شوید."
              : "حساب مدیر روی سرور تنظیم نشده است. متغیرهای ADMIN_USERNAME و ADMIN_PASSWORD را تنظیم کنید."}
          </p>
        </header>
        {configured && (
          <>
            <label className="field">
              <span>نام کاربری</span>
              <div className="input big">
                <User size={18} className="muted" />
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  dir="ltr"
                  autoFocus
                />
              </div>
            </label>
            <label className="field">
              <span>رمز عبور</span>
              <div className="input big">
                <Lock size={18} className="muted" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  dir="ltr"
                />
              </div>
            </label>
            {error && <p className="error-text">{error}</p>}
            <button className="btn primary lg block" disabled={busy || !username || !password}>
              {busy ? <Spinner /> : "ورود"}
            </button>
          </>
        )}
      </form>
    </>
  );
}
