// Reports for the operator's admin panel: what's happening across every
// guaranteed-plan circle, where the money went, who owes what, and the
// audit trail. Read-only; phones are masked.
import { HttpError } from "./errors.js";
import { planById, PLANS } from "../src/lib/plans.js";
import { drawAt, scheduleOf } from "../src/lib/schedule.js";

const FIVE_MINUTES = 5 * 60 * 1000;

export const maskPhone = (phone) => (phone ? `${phone.slice(0, 4)}***${phone.slice(-4)}` : null);

// Who a seat belongs to, as the operator should see it.
const seatOwner = (m) => (m.is_operator ? "operator" : m.is_bot ? "bot" : "member");

export function createOpsReports({ db, now = Date.now }) {
  const sum = async (sql, ...params) => (await db.get(sql, ...params)).total ?? 0;

  async function overview() {
    const byStatus = Object.fromEntries(
      (await db.all("SELECT status, COUNT(*) AS n FROM circles GROUP BY status")).map((r) => [r.status, r.n]),
    );
    const people = await db.get(
      `SELECT COUNT(*) AS seats, COUNT(DISTINCT m.phone) AS users FROM circle_members m
       JOIN circles c ON c.id = m.circle_id
       WHERE m.is_operator = 0 AND m.is_bot = 0 AND c.status IN ('forming', 'active', 'completed')`,
    );

    // Where each member installment came from. The operator's own share is
    // reported apart: it is Digipay's money, not collection.
    const methods = await db.all(
      `SELECT method, COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total FROM contributions
       WHERE status IN ('paid', 'covered') AND method != 'operator' GROUP BY method`,
    );
    const byMethod = Object.fromEntries(methods.map((r) => [r.method, { count: r.n, amount: r.total }]));
    const collectedByMembers = ["entry", "manual", "wallet"].reduce((t, k) => t + (byMethod[k]?.amount ?? 0), 0);
    const guaranteed = byMethod.guarantee?.amount ?? 0;
    const installments = methods.reduce((t, r) => t + r.n, 0);

    const paidOut = await db.get(
      `SELECT COALESCE(SUM(CASE WHEN m.is_operator = 1 THEN d.pot ELSE 0 END), 0) AS operator,
              COALESCE(SUM(CASE WHEN m.is_operator = 0 THEN d.pot ELSE 0 END), 0) AS members,
              COUNT(*) AS draws
       FROM circle_draws d JOIN circle_members m ON m.id = d.winner_member_id WHERE d.payout_ref IS NOT NULL`,
    );
    const openDebt = await sum(
      "SELECT COALESCE(SUM(amount), 0) AS total FROM contributions WHERE status = 'covered' AND settled_at IS NULL",
    );
    const recovered = await sum(
      "SELECT COALESCE(SUM(amount), 0) AS total FROM contributions WHERE status = 'covered' AND settled_at IS NOT NULL",
    );
    const debtors = (
      await db.get(
        "SELECT COUNT(DISTINCT member_id) AS n FROM contributions WHERE status = 'covered' AND settled_at IS NULL",
      )
    ).n;
    const refunds = await sum("SELECT COALESCE(SUM(amount), 0) AS total FROM ops_events WHERE kind = 'refund'");

    const started = await db.all("SELECT created_at, started_at FROM circles WHERE started_at IS NOT NULL");
    const fillTimes = started.map((c) => c.started_at - c.created_at);
    const fill = {
      count: fillTimes.length,
      averageMs: fillTimes.length ? Math.round(fillTimes.reduce((a, b) => a + b, 0) / fillTimes.length) : null,
      underFiveMinutes: fillTimes.filter((t) => t <= FIVE_MINUTES).length,
    };

    const active = await db.all(
      "SELECT id, plan_id, started_at, current_month, months FROM circles WHERE status = 'active'",
    );
    const upcoming = active
      .map((c) => ({ id: c.id, planId: c.plan_id, month: c.current_month, at: drawAt(c.started_at, c.current_month) }))
      .sort((a, b) => a.at - b.at)
      .slice(0, 6);

    const plans = [];
    for (const plan of PLANS) {
      const row = await db.get(
        `SELECT
           COALESCE(SUM(CASE WHEN status = 'forming' THEN 1 ELSE 0 END), 0) AS forming,
           COALESCE(SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END), 0) AS active,
           COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) AS completed,
           COALESCE(SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END), 0) AS expired
         FROM circles WHERE plan_id = ?`,
        plan.id,
      );
      plans.push({ id: plan.id, title: plan.title, size: plan.size, share: plan.share, ...row });
    }

    const family = await db.get("SELECT COUNT(*) AS funds, (SELECT COUNT(*) FROM fund_members) AS members FROM funds");

    return {
      circles: {
        forming: byStatus.forming ?? 0,
        active: byStatus.active ?? 0,
        completed: byStatus.completed ?? 0,
        expired: byStatus.expired ?? 0,
      },
      people: { users: people.users, seats: people.seats },
      money: {
        collectedByMembers,
        guaranteed,
        openDebt,
        recovered,
        debtors,
        refunds,
        paidOutToMembers: paidOut.members,
        paidOutToOperator: paidOut.operator,
        draws: paidOut.draws,
      },
      // Share of installments paid without the guarantee stepping in.
      collection: {
        installments,
        byMethod,
        paidRate: installments ? (installments - (byMethod.guarantee?.count ?? 0)) / installments : null,
      },
      fill,
      upcoming,
      plans,
      family: { funds: family.funds, members: family.members },
    };
  }

  async function circles() {
    const rows = await db.all(
      `SELECT c.*,
         (SELECT COUNT(*) FROM circle_members m WHERE m.circle_id = c.id) AS taken,
         (SELECT COALESCE(SUM(amount), 0) FROM contributions x
            WHERE x.circle_id = c.id AND x.status = 'covered' AND x.settled_at IS NULL) AS debt,
         (SELECT COUNT(*) FROM contributions x
            WHERE x.circle_id = c.id AND x.month = c.current_month AND x.method IS DISTINCT FROM 'operator') AS due_count,
         (SELECT COUNT(*) FROM contributions x
            WHERE x.circle_id = c.id AND x.month = c.current_month AND x.status = 'paid'
              AND x.method IS DISTINCT FROM 'operator') AS paid_count
       FROM circles c ORDER BY c.created_at DESC`,
    );
    return rows.map((c) => ({
      id: c.id,
      planId: c.plan_id,
      status: c.status,
      size: c.size,
      months: c.months,
      share: c.share,
      taken: c.taken,
      currentMonth: c.current_month,
      createdAt: c.created_at,
      startedAt: c.started_at,
      deadline: c.deadline,
      nextDrawAt: c.status === "active" ? drawAt(c.started_at, c.current_month) : null,
      thisMonth: c.status === "active" ? { paid: c.paid_count, of: c.due_count } : null,
      debt: c.debt,
    }));
  }

  async function circle(id) {
    const c = await db.get("SELECT * FROM circles WHERE id = ?", id);
    if (!c) throw new HttpError(404, "این دوره پیدا نشد.");
    const members = await db.all("SELECT * FROM circle_members WHERE circle_id = ? ORDER BY position", id);
    const contributions = await db.all(
      "SELECT member_id, month, amount, status, method, settled_at FROM contributions WHERE circle_id = ? ORDER BY month",
      id,
    );
    const draws = await db.all("SELECT * FROM circle_draws WHERE circle_id = ? ORDER BY month", id);
    const events = await db.all("SELECT * FROM ops_events WHERE circle_id = ? ORDER BY at DESC LIMIT 100", id);

    const paymentsOf = new Map(members.map((m) => [m.id, {}]));
    for (const x of contributions) {
      paymentsOf.get(x.member_id)[x.month] = {
        status: x.status === "covered" && x.settled_at ? "settled" : x.status,
        method: x.method,
        amount: x.amount,
      };
    }
    const positionOf = new Map(members.map((m) => [m.id, m.position]));

    return {
      circle: {
        id: c.id,
        planId: c.plan_id,
        title: planById(c.plan_id)?.title,
        status: c.status,
        size: c.size,
        months: c.months,
        share: c.share,
        pot: c.size * c.share,
        currentMonth: c.current_month,
        createdAt: c.created_at,
        startedAt: c.started_at,
        deadline: c.deadline,
        anchor: c.anchor,
        schedule: c.started_at ? scheduleOf(c.started_at, c.months) : [],
      },
      members: members.map((m) => {
        const payments = paymentsOf.get(m.id);
        const debt = Object.values(payments)
          .filter((p) => p.status === "covered")
          .reduce((t, p) => t + p.amount, 0);
        return {
          id: m.id,
          position: m.position,
          owner: seatOwner(m),
          phone: maskPhone(m.phone),
          wonMonth: m.won_month,
          joinedAt: m.joined_at,
          debt,
          payments,
        };
      }),
      draws: draws.map((d) => ({
        month: d.month,
        kind: d.kind,
        winnerPosition: positionOf.get(d.winner_member_id) ?? null,
        eligible: JSON.parse(d.eligible).length,
        pot: d.pot,
        paidOut: Boolean(d.payout_ref),
        payoutRef: d.payout_ref,
        at: d.created_at,
      })),
      events: events.map((e) => eventView(e, positionOf)),
    };
  }

  async function debtors() {
    const rows = await db.all(
      `SELECT x.circle_id, x.member_id, COUNT(*) AS months, SUM(x.amount) AS amount, MIN(x.paid_at) AS since,
              m.position, m.phone, m.is_bot, c.plan_id
       FROM contributions x
       JOIN circle_members m ON m.id = x.member_id
       JOIN circles c ON c.id = x.circle_id
       WHERE x.status = 'covered' AND x.settled_at IS NULL
       GROUP BY x.circle_id, x.member_id, m.position, m.phone, m.is_bot, c.plan_id
       ORDER BY amount DESC, since`,
    );
    return rows.map((r) => ({
      circleId: r.circle_id,
      planId: r.plan_id,
      position: r.position,
      owner: r.is_bot ? "bot" : "member",
      phone: maskPhone(r.phone),
      months: r.months,
      amount: r.amount,
      since: r.since,
    }));
  }

  async function events({ limit = 100, kind } = {}) {
    const n = Math.min(Math.max(Number(limit) || 100, 1), 500);
    const rows = kind
      ? await db.all("SELECT * FROM ops_events WHERE kind = ? ORDER BY at DESC LIMIT ?", kind, n)
      : await db.all("SELECT * FROM ops_events ORDER BY at DESC LIMIT ?", n);
    const plans = new Map((await db.all("SELECT id, plan_id FROM circles")).map((c) => [c.id, c.plan_id]));
    return rows.map((e) => ({ ...eventView(e), planId: plans.get(e.circle_id) ?? null }));
  }

  return { overview, circles, circle, debtors, events };
}

function eventView(e, positionOf) {
  return {
    id: e.id,
    at: e.at,
    kind: e.kind,
    circleId: e.circle_id,
    position: positionOf?.get(e.member_id) ?? null,
    phone: maskPhone(e.phone),
    amount: e.amount,
    detail: e.detail ? JSON.parse(e.detail) : null,
  };
}
