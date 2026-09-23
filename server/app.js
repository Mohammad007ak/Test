import express from "express";
import { createHash, randomBytes, randomInt } from "node:crypto";
import { transaction } from "./db.js";
import { HttpError } from "./errors.js";
import { createCircleService } from "./circles.js";
import { mountCircleRoutes } from "./circle-routes.js";
import { createDigipaySimulator } from "./digipay/simulator.js";
import { normalizePhone } from "../src/lib/phone.js";
import { currentMonthKey } from "../src/lib/jalali.js";
import {
  createLoan,
  fundBalance,
  isValidState,
  listDues,
  loanProgress,
  lotteryEntries,
  newId,
  overdueDues,
  pickWinner,
  sum,
} from "../src/lib/fund.js";

const MINUTE = 60 * 1000;
const CODE_TTL = 2 * MINUTE;
const RESEND_GAP = MINUTE;
const SEND_WINDOW = 60 * MINUTE;
const MAX_SENDS_PER_WINDOW = 5;
const MAX_CODE_ATTEMPTS = 5;
const SESSION_TTL = 30 * 24 * 60 * MINUTE;
const MAX_FUNDS_PER_OWNER = 20;

const sha256 = (value) => createHash("sha256").update(value).digest("hex");
const secureRandom = () => randomInt(0, 2 ** 47) / 2 ** 47;
const toLatinDigits = (value) => String(value ?? "").replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d));

function parseCookies(header = "") {
  return Object.fromEntries(
    header
      .split(";")
      .map((part) => part.trim().split("="))
      .filter(([key, value]) => key && value)
      .map(([key, value]) => [key, decodeURIComponent(value)]),
  );
}

export function createApp({
  db,
  sendCode = null,
  production = false,
  now = Date.now,
  random = secureRandom,
  digipay = createDigipaySimulator(),
  opsPhones = [],
  formTimeoutMs,
}) {
  const app = express();
  app.use(express.json({ limit: "2mb" }));

  // Mutating requests must be JSON: a cross-site form post can't send that
  // without a CORS preflight, which together with SameSite cookies blocks CSRF.
  app.use("/api", (req, res, next) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(req.method) && !req.is("application/json")) {
      return res.status(415).json({ error: "درخواست نامعتبر است." });
    }
    next();
  });

  const cookieOptions = {
    httpOnly: true,
    sameSite: "lax",
    secure: production,
    path: "/",
  };

  function currentPhone(req) {
    const token = parseCookies(req.headers.cookie).sid;
    if (!token) return null;
    const session = db
      .prepare("SELECT phone FROM sessions WHERE token_hash = ? AND expires_at > ?")
      .get(sha256(token), now());
    return session?.phone ?? null;
  }

  function requireLogin(req, res, next) {
    req.phone = currentPhone(req);
    if (!req.phone) return res.status(401).json({ error: "ابتدا وارد شوید." });
    next();
  }

  function loadFund(id) {
    const row = db.prepare("SELECT * FROM funds WHERE id = ?").get(id);
    if (!row) throw new HttpError(404, "صندوق پیدا نشد.");
    return { ...row, data: JSON.parse(row.data) };
  }

  // Report "not found" to non-managers so fund ids can't be probed.
  function loadManagedFund(req) {
    const fund = loadFund(req.params.id);
    if (fund.owner_phone !== req.phone) throw new HttpError(404, "صندوق پیدا نشد.");
    return fund;
  }

  function syncMembers(fundId, data) {
    db.prepare("DELETE FROM fund_members WHERE fund_id = ?").run(fundId);
    if (data.demo) return;
    const insert = db.prepare("INSERT INTO fund_members (fund_id, member_id, phone) VALUES (?, ?, ?)");
    for (const member of data.members) {
      const phone = normalizePhone(member.phone);
      if (phone) insert.run(fundId, member.id, phone);
    }
  }

  function writeFund(id, data, version) {
    db.prepare("UPDATE funds SET data = ?, version = ?, updated_at = ? WHERE id = ?").run(
      JSON.stringify(data),
      version,
      now(),
      id,
    );
    syncMembers(id, data);
  }

  function validData(data) {
    if (!isValidState(data)) throw new HttpError(400, "اطلاعات صندوق معتبر نیست.");
    return { ...data, fund: { cycle: 1, ...data.fund } };
  }

  function startSession(res, phone) {
    const token = randomBytes(32).toString("base64url");
    transaction(db, () => {
      db.prepare("DELETE FROM sessions WHERE expires_at <= ?").run(now());
      db.prepare("INSERT INTO sessions (token_hash, phone, expires_at) VALUES (?, ?, ?)").run(
        sha256(token),
        phone,
        now() + SESSION_TTL,
      );
    });
    res.cookie("sid", token, { ...cookieOptions, maxAge: SESSION_TTL });
  }

  const route = (handler) => async (req, res, next) => {
    try {
      await handler(req, res);
    } catch (error) {
      next(error);
    }
  };

  // ---------- auth ----------

  app.post(
    "/api/auth/request-code",
    route(async (req, res) => {
      const phone = normalizePhone(req.body.phone);
      if (!phone) throw new HttpError(400, "شماره موبایل معتبر نیست.");

      const t = now();
      const previous = db.prepare("SELECT * FROM otp_codes WHERE phone = ?").get(phone);
      const sameWindow = previous && t - previous.window_start < SEND_WINDOW;
      const sentInWindow = sameWindow ? previous.sent_in_window : 0;
      if (sentInWindow >= MAX_SENDS_PER_WINDOW) {
        throw new HttpError(429, "تعداد درخواست‌ها زیاد است. یک ساعت دیگر تلاش کنید.");
      }
      if (previous && previous.expires_at - CODE_TTL + RESEND_GAP > t) {
        throw new HttpError(429, "لطفاً یک دقیقه صبر کنید و دوباره تلاش کنید.");
      }
      if (!sendCode && production) throw new HttpError(500, "سرویس پیامک تنظیم نشده است.");

      const code = String(randomInt(0, 100000)).padStart(5, "0");
      db.prepare(
        `INSERT INTO otp_codes (phone, code_hash, expires_at, attempts, window_start, sent_in_window)
         VALUES (?, ?, ?, 0, ?, ?)
         ON CONFLICT (phone) DO UPDATE SET code_hash = excluded.code_hash, expires_at = excluded.expires_at,
           attempts = 0, window_start = excluded.window_start, sent_in_window = excluded.sent_in_window`,
      ).run(phone, sha256(code), t + CODE_TTL, sameWindow ? previous.window_start : t, sentInWindow + 1);

      if (sendCode) {
        try {
          await sendCode(phone, code);
        } catch (error) {
          console.error("SMS send failed:", error.message);
          throw new HttpError(502, "ارسال پیامک ناموفق بود. دوباره تلاش کنید.");
        }
        return res.json({ ok: true });
      }
      console.log(`[dev] login code for ${phone}: ${code}`);
      res.json({ ok: true, devCode: code });
    }),
  );

  app.post(
    "/api/auth/verify",
    route(async (req, res) => {
      const phone = normalizePhone(req.body.phone);
      const code = toLatinDigits(req.body.code).trim();
      const row = phone && db.prepare("SELECT * FROM otp_codes WHERE phone = ?").get(phone);
      if (!row || row.expires_at <= now()) {
        throw new HttpError(400, "کد منقضی شده است. دوباره درخواست کنید.");
      }
      if (row.attempts >= MAX_CODE_ATTEMPTS) {
        throw new HttpError(429, "تعداد تلاش‌ها زیاد بود. کد جدید درخواست کنید.");
      }
      if (sha256(code) !== row.code_hash) {
        db.prepare("UPDATE otp_codes SET attempts = attempts + 1 WHERE phone = ?").run(phone);
        throw new HttpError(400, "کد وارد شده اشتباه است.");
      }

      // Keep the send counter so verifying doesn't reset the rate limit.
      db.prepare("UPDATE otp_codes SET code_hash = '', expires_at = 0 WHERE phone = ?").run(phone);
      startSession(res, phone);
      res.json({ phone });
    }),
  );

  // Inside the Digipay app the user is already signed in; the host hands us
  // a launch token that Digipay vouches for, so no SMS code is needed.
  app.post(
    "/api/auth/digipay",
    route(async (req, res) => {
      const identity = await digipay.identity.verifyLaunchToken(req.body.token);
      const phone = identity && normalizePhone(identity.phone);
      if (!phone) throw new HttpError(401, "ورود از طریق دیجی‌پی تأیید نشد.");
      startSession(res, phone);
      res.json({ phone });
    }),
  );

  app.post("/api/auth/logout", (req, res) => {
    const token = parseCookies(req.headers.cookie).sid;
    if (token) db.prepare("DELETE FROM sessions WHERE token_hash = ?").run(sha256(token));
    res.clearCookie("sid", cookieOptions);
    res.json({ ok: true });
  });

  app.get("/api/me", requireLogin, (req, res) => res.json({ phone: req.phone }));

  // ---------- funds (manager) ----------

  app.get(
    "/api/funds",
    requireLogin,
    route((req, res) => {
      const managed = db
        .prepare("SELECT id, data FROM funds WHERE owner_phone = ? ORDER BY created_at")
        .all(req.phone)
        .map((row) => {
          const data = JSON.parse(row.data);
          const late = new Set(overdueDues(data, currentMonthKey(new Date(now()))).map((d) => d.memberId));
          return {
            id: row.id,
            name: data.fund.name,
            members: data.members.length,
            balance: fundBalance(data),
            lateMembers: late.size,
          };
        });
      const member = db
        .prepare(
          `SELECT DISTINCT f.id, f.data FROM fund_members m JOIN funds f ON f.id = m.fund_id
           WHERE m.phone = ? AND f.owner_phone != ? ORDER BY f.created_at`,
        )
        .all(req.phone, req.phone)
        .map((row) => ({ id: row.id, name: JSON.parse(row.data).fund.name }));
      res.json({ managed, member });
    }),
  );

  app.post(
    "/api/funds",
    requireLogin,
    route((req, res) => {
      const data = validData(req.body.data);
      const { count } = db.prepare("SELECT COUNT(*) AS count FROM funds WHERE owner_phone = ?").get(req.phone);
      if (count >= MAX_FUNDS_PER_OWNER) throw new HttpError(400, "به سقف تعداد صندوق رسیده‌اید.");

      const id = newId();
      transaction(db, () => {
        db.prepare(
          "INSERT INTO funds (id, owner_phone, data, version, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
        ).run(id, req.phone, JSON.stringify(data), now(), now());
        syncMembers(id, data);
      });
      res.status(201).json({ id, data, version: 1 });
    }),
  );

  app.get(
    "/api/funds/:id",
    requireLogin,
    route((req, res) => {
      const fund = loadManagedFund(req);
      res.json({ id: fund.id, data: fund.data, version: fund.version });
    }),
  );

  app.put(
    "/api/funds/:id",
    requireLogin,
    route((req, res) => {
      const fund = loadManagedFund(req);
      if (req.body.version !== fund.version) {
        throw new HttpError(409, "این صندوق در جای دیگری تغییر کرده است.", {
          data: fund.data,
          version: fund.version,
        });
      }
      const data = validData(req.body.data);
      transaction(db, () => writeFund(fund.id, data, fund.version + 1));
      res.json({ version: fund.version + 1 });
    }),
  );

  app.delete(
    "/api/funds/:id",
    requireLogin,
    route((req, res) => {
      const fund = loadManagedFund(req);
      db.prepare("DELETE FROM funds WHERE id = ?").run(fund.id);
      res.json({ ok: true });
    }),
  );

  // ---------- lottery ----------
  // Draws happen on the server with a secure random source and are logged,
  // so a manager can't quietly re-roll until a friend wins.

  app.post(
    "/api/funds/:id/draws",
    requireLogin,
    route((req, res) => {
      const fund = loadManagedFund(req);
      const entries = lotteryEntries(fund.data);
      if (!entries.length) throw new HttpError(400, "همه‌ی اعضا در این دور وام گرفته‌اند.");
      if (fundBalance(fund.data) < fund.data.fund.loanAmount) {
        throw new HttpError(400, "موجودی صندوق برای یک وام کافی نیست.");
      }

      const winner = pickWinner(entries, random);
      const draw = {
        id: newId(),
        month: currentMonthKey(new Date(now())),
        winnerId: winner.id,
        winnerName: winner.name,
      };
      transaction(db, () => {
        db.prepare(
          "UPDATE draws SET status = 'cancelled', resolved_at = ? WHERE fund_id = ? AND status = 'pending'",
        ).run(now(), fund.id);
        db.prepare(
          `INSERT INTO draws (id, fund_id, month, winner_member_id, winner_name, entries, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)`,
        ).run(
          draw.id,
          fund.id,
          draw.month,
          winner.id,
          winner.name,
          JSON.stringify(entries.map((e) => ({ memberId: e.member.id, name: e.member.name, tickets: e.tickets }))),
          now(),
        );
      });
      res.status(201).json({ draw });
    }),
  );

  function loadPendingDraw(fundId, drawId) {
    const draw = db.prepare("SELECT * FROM draws WHERE id = ? AND fund_id = ?").get(drawId, fundId);
    if (!draw) throw new HttpError(404, "قرعه پیدا نشد.");
    if (draw.status !== "pending") throw new HttpError(400, "این قرعه قبلاً نهایی شده است.");
    return draw;
  }

  app.post(
    "/api/funds/:id/draws/:drawId/confirm",
    requireLogin,
    route((req, res) => {
      const fund = loadManagedFund(req);
      const draw = loadPendingDraw(fund.id, req.params.drawId);
      if (!fund.data.members.some((m) => m.id === draw.winner_member_id)) {
        throw new HttpError(400, "برنده دیگر عضو صندوق نیست.");
      }
      const loan = { ...createLoan(fund.data.fund, draw.winner_member_id, draw.month), drawId: draw.id };
      const data = { ...fund.data, loans: [...fund.data.loans, loan] };
      transaction(db, () => {
        writeFund(fund.id, data, fund.version + 1);
        db.prepare("UPDATE draws SET status = 'confirmed', resolved_at = ? WHERE id = ?").run(now(), draw.id);
      });
      res.json({ data, version: fund.version + 1 });
    }),
  );

  app.post(
    "/api/funds/:id/draws/:drawId/cancel",
    requireLogin,
    route((req, res) => {
      const fund = loadManagedFund(req);
      const draw = loadPendingDraw(fund.id, req.params.drawId);
      db.prepare("UPDATE draws SET status = 'cancelled', resolved_at = ? WHERE id = ?").run(now(), draw.id);
      res.json({ ok: true });
    }),
  );

  // ---------- member view ----------
  // What an ordinary member may see: their own ledger, plus the fund-wide
  // facts that make the fund trustworthy (balance, loans, every draw).

  app.get(
    "/api/funds/:id/view",
    requireLogin,
    route((req, res) => {
      const fund = loadFund(req.params.id);
      const isManager = fund.owner_phone === req.phone;
      const membership = db
        .prepare("SELECT member_id FROM fund_members WHERE fund_id = ? AND phone = ?")
        .get(fund.id, req.phone);
      if (!isManager && !membership) throw new HttpError(404, "صندوق پیدا نشد.");

      const { data } = fund;
      const month = currentMonthKey(new Date(now()));
      const nameOf = new Map(data.members.map((m) => [m.id, m.name]));
      const member = membership && data.members.find((m) => m.id === membership.member_id);

      let me = null;
      if (member) {
        const dues = listDues(data, month).filter((d) => d.memberId === member.id);
        const overdue = dues.filter((d) => !d.paid && d.month < month);
        me = {
          name: member.name,
          shares: member.shares,
          overdueAmount: sum(overdue),
          dues: dues
            .map(({ type, month: m, amount, paid }) => ({ type, month: m, amount, paid }))
            .sort((a, b) => b.month.localeCompare(a.month) || a.type.localeCompare(b.type)),
          loans: data.loans
            .filter((l) => l.memberId === member.id)
            .map((l) => ({
              amount: l.amount,
              installments: l.installments,
              firstInstallmentMonth: l.firstInstallmentMonth,
              ...loanProgress(data, l),
            })),
        };
      }

      const draws = db
        .prepare("SELECT month, winner_name, status, created_at FROM draws WHERE fund_id = ? ORDER BY created_at DESC")
        .all(fund.id)
        .map((d) => ({ month: d.month, winnerName: d.winner_name, status: d.status, createdAt: d.created_at }));

      res.json({
        fund: {
          name: data.fund.name,
          contribution: data.fund.contribution,
          loanAmount: data.fund.loanAmount,
          installments: data.fund.installments,
          cycle: data.fund.cycle,
          cardNumber: data.fund.cardNumber ?? "",
          cardHolder: data.fund.cardHolder ?? "",
        },
        isManager,
        currentMonth: month,
        balance: fundBalance(data),
        memberCount: data.members.length,
        totalShares: sum(data.members, (m) => m.shares),
        me,
        loans: [...data.loans]
          .sort((a, b) => b.drawMonth.localeCompare(a.drawMonth))
          .map((l) => ({
            memberName: nameOf.get(l.memberId) ?? "عضو سابق",
            amount: l.amount,
            drawMonth: l.drawMonth,
            viaDraw: Boolean(l.drawId),
          })),
        draws,
      });
    }),
  );

  const circles = createCircleService({ db, digipay, now, formTimeoutMs });
  // The hosting process calls this on a timer so draws happen on their day
  // even when nobody opens the app.
  app.locals.runScheduledJobs = () => circles.runDueDraws();

  mountCircleRoutes(app, {
    service: circles,
    requireLogin,
    route,
    // Ops tools (simulating months, filling circles) are open to everyone
    // in development and to OPS_PHONES in production.
    isOps: (phone) => (production ? opsPhones.includes(phone) : true),
    simulator: digipay.name === "simulator",
  });

  app.use("/api", (req, res) => res.status(404).json({ error: "مسیر پیدا نشد." }));

  // eslint-disable-next-line no-unused-vars
  app.use((error, req, res, next) => {
    if (error instanceof HttpError) {
      return res.status(error.status).json({ error: error.message, ...error.extra });
    }
    if (error.type === "entity.parse.failed") return res.status(400).json({ error: "درخواست نامعتبر است." });
    console.error(error);
    res.status(500).json({ error: "خطای داخلی سرور." });
  });

  return app;
}
