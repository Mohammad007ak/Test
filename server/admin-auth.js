// Username/password sign-in for the admin panel, separate from members'
// phone login. The credentials come from ADMIN_USERNAME / ADMIN_PASSWORD;
// only their scrypt hashes are kept in memory, sessions live in the
// database, and repeated wrong passwords lock the address out for a while.
import { createHash, randomBytes, scryptSync, timingSafeEqual } from "node:crypto";
import { HttpError } from "./errors.js";

const MINUTE = 60 * 1000;
const SESSION_TTL = 12 * 60 * MINUTE;
const MAX_FAILURES = 5;
const LOCKOUT = 15 * MINUTE;
const MIN_PASSWORD_LENGTH = 10;

const sha256 = (value) => createHash("sha256").update(value).digest("hex");
const SALT = randomBytes(16);
const slowHash = (value) => scryptSync(String(value ?? ""), SALT, 32);

export function createAdminAuth({ db, username, password, production = false, now = Date.now, parseCookies }) {
  const configured = Boolean(username && password);
  if (configured && production && password.length < MIN_PASSWORD_LENGTH) {
    throw new Error(`Refusing to start: ADMIN_PASSWORD must be at least ${MIN_PASSWORD_LENGTH} characters.`);
  }
  const userHash = configured ? slowHash(username) : null;
  const passHash = configured ? slowHash(password) : null;
  const cookieOptions = { httpOnly: true, sameSite: "strict", secure: production, path: "/" };

  // Failed attempts per client address: { count, until }.
  const failures = new Map();

  async function currentAdmin(req) {
    const token = parseCookies(req.headers.cookie).asid;
    if (!token) return null;
    const row = await db.get(
      "SELECT username FROM admin_sessions WHERE token_hash = ? AND expires_at > ?",
      sha256(token),
      now(),
    );
    return row?.username ?? null;
  }

  async function login(req, res) {
    if (!configured) throw new HttpError(404, "ورود مدیر تنظیم نشده است.");
    const key = req.ip ?? "unknown";
    const f = failures.get(key);
    if (f && f.count >= MAX_FAILURES && f.until > now()) {
      throw new HttpError(429, "تلاش‌های ناموفق زیاد بود. ۱۵ دقیقه‌ی دیگر دوباره امتحان کنید.");
    }
    // Hash both fields every time, so a wrong username takes as long as a
    // wrong password.
    const userOk = timingSafeEqual(slowHash(req.body.username), userHash);
    const passOk = timingSafeEqual(slowHash(req.body.password), passHash);
    if (!userOk || !passOk) {
      const count = (f && f.until > now() ? f.count : 0) + 1;
      failures.set(key, { count, until: now() + LOCKOUT });
      throw new HttpError(401, "نام کاربری یا رمز عبور اشتباه است.");
    }
    failures.delete(key);
    const token = randomBytes(32).toString("base64url");
    await db.transaction(async (tx) => {
      await tx.run("DELETE FROM admin_sessions WHERE expires_at <= ?", now());
      await tx.run(
        "INSERT INTO admin_sessions (token_hash, username, expires_at) VALUES (?, ?, ?)",
        sha256(token),
        username,
        now() + SESSION_TTL,
      );
    });
    res.cookie("asid", token, { ...cookieOptions, maxAge: SESSION_TTL });
    return { username };
  }

  async function logout(req, res) {
    const token = parseCookies(req.headers.cookie).asid;
    if (token) await db.run("DELETE FROM admin_sessions WHERE token_hash = ?", sha256(token));
    res.clearCookie("asid", cookieOptions);
  }

  return { configured, currentAdmin, login, logout };
}
