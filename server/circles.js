// Guaranteed circles: the paid product, with Digipay as operator.
//
// A circle runs one plan. It fills up while "forming", then runs one month
// per cycle. Each month every member owes one share and one member receives
// the pot (size × share):
//   month 1      → the operator (position 1), always;
//   last month   → whoever hasn't received yet;
//   other months → a provably fair lottery among members who haven't
//                  received yet and don't owe anything.
// Members pay each month through the cash gateway. Whatever is still unpaid
// when the month closes is debited from their Digipay wallet (they agree to
// this in the terms); if the wallet can't cover it, the operator pays in
// their place ("covered") so the pot is always whole, and the member owes it.
//
// A forming circle waits for members until its deadline; if it doesn't fill
// in time it expires and everyone in it is released.

import { transaction } from "./db.js";
import { HttpError } from "./errors.js";
import { planById, PLANS, potOf } from "../src/lib/plans.js";
import { buildChain, nonceDigest, pickWinner, randomHex } from "../src/lib/fairness.js";
import { newId } from "../src/lib/fund.js";

const NONCE = /^[0-9a-f]{32,64}$/;

const HOUR = 60 * 60 * 1000;

export function createCircleService({ db, digipay, now = Date.now, formTimeoutMs = HOUR }) {
  const q = (sql) => db.prepare(sql);

  const getCircle = (id) => q("SELECT * FROM circles WHERE id = ?").get(id);
  const membersOf = (circleId) =>
    q("SELECT * FROM circle_members WHERE circle_id = ? ORDER BY position").all(circleId);

  // ---------- forming ----------

  async function createCircle(plan) {
    const secret = randomHex();
    const [anchor] = await buildChain(secret, plan.months);
    const id = newId();
    transaction(db, () => {
      q(
        `INSERT INTO circles (id, plan_id, status, size, months, share, chain_secret, anchor, created_at, deadline)
         VALUES (?, ?, 'forming', ?, ?, ?, ?, ?, ?, ?)`,
      ).run(id, plan.id, plan.size, plan.months, plan.share, secret, anchor, now(), now() + formTimeoutMs);
      q(
        `INSERT INTO circle_members (id, circle_id, position, phone, is_operator, nonce, pay_method, joined_at)
         VALUES (?, ?, 1, NULL, 1, ?, 'operator', ?)`,
      ).run(newId(), id, randomHex(16), now());
    });
    return id;
  }

  async function openCircleFor(plan) {
    const open = q(
      "SELECT id FROM circles WHERE plan_id = ? AND status = 'forming' AND deadline > ? ORDER BY created_at LIMIT 1",
    ).get(plan.id, now());
    return open?.id ?? createCircle(plan);
  }

  // Release everyone from circles that didn't fill before their deadline.
  async function expireStale() {
    const stale = q("SELECT id FROM circles WHERE status = 'forming' AND deadline <= ?").all(now());
    for (const { id } of stale) {
      const expired = q("UPDATE circles SET status = 'expired' WHERE id = ? AND status = 'forming'").run(id).changes;
      if (!expired) continue;
      for (const m of membersOf(id)) {
        if (m.mandate_id) await digipay.payments.revokeMandate({ mandateId: m.mandate_id });
      }
    }
  }

  function openMonth(circleId, month, share) {
    for (const m of membersOf(circleId)) {
      const operator = Boolean(m.is_operator);
      q(
        `INSERT INTO contributions (circle_id, member_id, month, amount, status, method, paid_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
      ).run(circleId, m.id, month, share, operator ? "paid" : "due", operator ? "operator" : null, operator ? now() : null);
    }
  }

  // Must run inside a transaction, right after the last seat is taken.
  function startCircle(circle) {
    q("UPDATE circles SET status = 'active', started_at = ?, current_month = 1 WHERE id = ?").run(now(), circle.id);
    openMonth(circle.id, 1, circle.share);
  }

  async function publishNonceDigest(circleId) {
    const circle = getCircle(circleId);
    if (circle.status === "forming" || circle.nonce_digest) return;
    const digest = await nonceDigest(membersOf(circleId).map((m) => m.nonce));
    q("UPDATE circles SET nonce_digest = ? WHERE id = ? AND nonce_digest IS NULL").run(digest, circleId);
  }

  function committedMonthly(phone) {
    return q(
      `SELECT COALESCE(SUM(c.share), 0) AS total FROM circle_members m JOIN circles c ON c.id = m.circle_id
       WHERE m.phone = ? AND c.status IN ('forming', 'active')`,
    ).get(phone).total;
  }

  async function eligibility(phone) {
    const score = await digipay.scoring.check(phone);
    const committed = committedMonthly(phone);
    return {
      approved: Boolean(score.approved),
      monthlyLimit: score.monthlyLimit,
      committed,
      available: Math.max(0, score.monthlyLimit - committed),
    };
  }

  async function join({ phone, planId, nonce }) {
    const plan = planById(planId);
    if (!plan) throw new HttpError(404, "این طرح پیدا نشد.");
    await expireStale();
    const already = q(
      `SELECT 1 FROM circle_members m JOIN circles c ON c.id = m.circle_id
       WHERE m.phone = ? AND c.plan_id = ? AND c.status IN ('forming', 'active')`,
    ).get(phone, plan.id);
    if (already) throw new HttpError(409, "شما در یک دوره‌ی فعال از همین طرح عضو هستید.");

    const e = await eligibility(phone);
    if (!e.approved) throw new HttpError(403, "در حال حاضر امکان عضویت در طرح‌ها برای شما فعال نیست.");
    if (e.available < plan.share) {
      throw new HttpError(403, "سقف اعتبار ماهانه‌ی شما برای این طرح کافی نیست. طرح کوچک‌تری را امتحان کنید.");
    }

    // The wallet-debit fallback the member agrees to in the terms.
    const mandate = await digipay.payments.createMandate({ phone, monthlyAmount: plan.share, months: plan.months });
    // A nonce from the member's own device: entropy the server couldn't know
    // when it committed to the hash chain.
    const memberNonce = NONCE.test(nonce ?? "") ? nonce : randomHex(16);

    for (let attempt = 0; attempt < 3; attempt++) {
      const circleId = await openCircleFor(plan);
      const joined = transaction(db, () => {
        const circle = getCircle(circleId);
        const taken = q("SELECT COUNT(*) AS n FROM circle_members WHERE circle_id = ?").get(circleId).n;
        if (circle.status !== "forming" || taken >= circle.size) return null;
        const memberId = newId();
        q(
          `INSERT INTO circle_members (id, circle_id, position, phone, nonce, pay_method, mandate_id, joined_at)
           VALUES (?, ?, ?, ?, ?, 'manual', ?, ?)`,
        ).run(memberId, circleId, taken + 1, phone, memberNonce, mandate.mandateId, now());
        if (taken + 1 === circle.size) startCircle(circle);
        return { circleId, memberId };
      });
      if (joined) {
        await publishNonceDigest(joined.circleId);
        return joined;
      }
    }
    throw new HttpError(503, "لطفاً دوباره تلاش کنید.");
  }

  // Leaving is only possible while waiting for the circle to fill. Seats
  // behind the leaver move up so positions stay 1..n.
  async function leave({ phone, circleId }) {
    const member = memberFor(phone, circleId);
    const left = transaction(db, () => {
      if (getCircle(circleId).status !== "forming") return false;
      q("DELETE FROM circle_members WHERE id = ?").run(member.id);
      q("UPDATE circle_members SET position = -position WHERE circle_id = ? AND position > ?").run(circleId, member.position);
      q("UPDATE circle_members SET position = -position - 1 WHERE circle_id = ? AND position < 0").run(circleId);
      return true;
    });
    if (!left) throw new HttpError(400, "گروه شروع شده و دیگر نمی‌شود از آن خارج شد.");
    if (member.mandate_id) await digipay.payments.revokeMandate({ mandateId: member.mandate_id });
  }

  // ---------- running ----------

  async function closeMonth(circleId) {
    const claimed = q(
      "UPDATE circles SET closing = 1 WHERE id = ? AND status = 'active' AND closing = 0",
    ).run(circleId).changes;
    if (!claimed) throw new HttpError(409, "این دوره فعال نیست یا در حال پردازش است.");

    try {
      await publishNonceDigest(circleId);
      const circle = getCircle(circleId);
      const month = circle.current_month;
      const members = membersOf(circleId);

      // 1. Debit the wallet of anyone who hasn't paid through the gateway.
      const due = q("SELECT * FROM contributions WHERE circle_id = ? AND month = ? AND status = 'due'").all(
        circleId,
        month,
      );
      for (const d of due) {
        const member = members.find((m) => m.id === d.member_id);
        if (member.is_operator || !member.mandate_id) continue;
        const charge = await digipay.payments.charge({
          mandateId: member.mandate_id,
          amount: d.amount,
          ref: `${circleId}:${month}:${member.id}`,
        });
        if (charge.ok) {
          q(
            `UPDATE contributions SET status = 'paid', method = 'wallet', ref = ?, paid_at = ?
             WHERE circle_id = ? AND member_id = ? AND month = ? AND status = 'due'`,
          ).run(charge.ref, now(), circleId, member.id, month);
        }
      }

      // 2. Pick this month's recipient.
      const waiting = members.filter((m) => m.won_month === null);
      let draw;
      if (month === 1) {
        const operator = members.find((m) => m.is_operator);
        draw = { kind: "operator", winner: operator.id, eligible: [operator.id] };
      } else if (waiting.length === 1) {
        draw = { kind: "last", winner: waiting[0].id, eligible: [waiting[0].id] };
      } else {
        const owing = new Set(
          q(
            `SELECT DISTINCT member_id FROM contributions WHERE circle_id = ?
             AND ((status = 'covered' AND settled_at IS NULL) OR (month = ? AND status = 'due'))`,
          )
            .all(circleId, month)
            .map((r) => r.member_id),
        );
        let eligible = waiting.filter((m) => !owing.has(m.id)).map((m) => m.id);
        if (eligible.length === 0) eligible = waiting.map((m) => m.id);
        const drawNo = q("SELECT COUNT(*) AS n FROM circle_draws WHERE circle_id = ? AND kind = 'lottery'").get(circleId).n + 1;
        const chain = await buildChain(circle.chain_secret, circle.months);
        const reveal = chain[drawNo];
        const { seed, winner } = await pickWinner({ reveal, digest: getCircle(circleId).nonce_digest, month, eligible });
        draw = { kind: "lottery", drawNo, reveal, seed, winner, eligible };
      }

      // 3. Record it: the guarantee covers anyone still unpaid.
      const pot = circle.size * circle.share;
      transaction(db, () => {
        q(
          `UPDATE contributions SET status = 'covered', method = 'guarantee', paid_at = ?
           WHERE circle_id = ? AND month = ? AND status = 'due'`,
        ).run(now(), circleId, month);
        q(
          `INSERT INTO circle_draws (circle_id, month, kind, draw_no, reveal, seed, eligible, winner_member_id, pot, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        ).run(
          circleId,
          month,
          draw.kind,
          draw.drawNo ?? null,
          draw.reveal ?? null,
          draw.seed ?? null,
          JSON.stringify(draw.eligible),
          draw.winner,
          pot,
          now(),
        );
        q("UPDATE circle_members SET won_month = ? WHERE id = ?").run(month, draw.winner);
        if (month === circle.months) {
          q("UPDATE circles SET status = 'completed', closing = 0 WHERE id = ?").run(circleId);
        } else {
          q("UPDATE circles SET current_month = ?, closing = 0 WHERE id = ?").run(month + 1, circleId);
          openMonth(circleId, month + 1, circle.share);
        }
      });

      // 4. Pay the pot out. A failed payout can be retried; the draw stands.
      const recipient = members.find((m) => m.id === draw.winner);
      const payout = await digipay.payouts.send({
        phone: recipient.phone,
        operator: Boolean(recipient.is_operator),
        amount: pot,
        ref: `${circleId}:${month}`,
      });
      q("UPDATE circle_draws SET payout_ref = ? WHERE circle_id = ? AND month = ?").run(payout.ref, circleId, month);
      return { month, kind: draw.kind, winner: draw.winner, pot };
    } catch (error) {
      q("UPDATE circles SET closing = 0 WHERE id = ?").run(circleId);
      throw error;
    }
  }

  // ---------- manual payments ----------

  function memberFor(phone, circleId) {
    const member = q("SELECT * FROM circle_members WHERE circle_id = ? AND phone = ?").get(circleId, phone);
    if (!member) throw new HttpError(404, "این دوره پیدا نشد.");
    return member;
  }

  const outstandingOf = (circleId, memberId) =>
    q(
      `SELECT month, amount, status FROM contributions WHERE circle_id = ? AND member_id = ?
       AND (status = 'due' OR (status = 'covered' AND settled_at IS NULL)) ORDER BY month`,
    ).all(circleId, memberId);

  async function startCheckout({ phone, circleId }) {
    const member = memberFor(phone, circleId);
    const items = outstandingOf(circleId, member.id);
    if (items.length === 0) throw new HttpError(400, "پرداخت معوقی ندارید.");
    const amount = items.reduce((t, i) => t + i.amount, 0);
    const id = newId();
    const checkout = await digipay.payments.createCheckout({ phone, amount, ref: id });
    q(
      `INSERT INTO checkouts (id, phone, circle_id, member_id, items, amount, status, ref, created_at)
       VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)`,
    ).run(id, phone, circleId, member.id, JSON.stringify(items.map((i) => i.month)), amount, checkout.checkoutRef, now());
    return { checkoutId: id, redirectUrl: checkout.url ?? null };
  }

  function getCheckout(phone, id) {
    const checkout = q("SELECT * FROM checkouts WHERE id = ? AND phone = ?").get(id, phone);
    if (!checkout) throw new HttpError(404, "پرداخت پیدا نشد.");
    const circle = getCircle(checkout.circle_id);
    return {
      id: checkout.id,
      amount: checkout.amount,
      status: checkout.status,
      months: JSON.parse(checkout.items),
      circleId: checkout.circle_id,
      planId: circle.plan_id,
    };
  }

  async function completeCheckout({ phone, id, action }) {
    const checkout = q("SELECT * FROM checkouts WHERE id = ? AND phone = ?").get(id, phone);
    if (!checkout) throw new HttpError(404, "پرداخت پیدا نشد.");
    if (checkout.status !== "pending") throw new HttpError(400, "این پرداخت قبلاً نهایی شده است.");
    const result = await digipay.payments.verifyCheckout({ checkoutRef: checkout.ref, action });
    transaction(db, () => {
      if (!result.ok) {
        q("UPDATE checkouts SET status = 'cancelled' WHERE id = ?").run(id);
        return;
      }
      for (const month of JSON.parse(checkout.items)) {
        const args = [checkout.circle_id, checkout.member_id, month];
        q(
          `UPDATE contributions SET status = 'paid', method = 'manual', ref = ?, paid_at = ?
           WHERE circle_id = ? AND member_id = ? AND month = ? AND status = 'due'`,
        ).run(result.ref, now(), ...args);
        q(
          `UPDATE contributions SET settled_at = ?
           WHERE circle_id = ? AND member_id = ? AND month = ? AND status = 'covered' AND settled_at IS NULL`,
        ).run(now(), ...args);
      }
      q("UPDATE checkouts SET status = 'paid', ref = ? WHERE id = ?").run(result.ref, id);
    });
    return { ok: result.ok, circleId: checkout.circle_id };
  }

  // ---------- views ----------

  async function planSummaries() {
    await expireStale();
    return PLANS.map((plan) => {
      const open = q(
        `SELECT c.id, COUNT(m.id) AS taken FROM circles c JOIN circle_members m ON m.circle_id = c.id
         WHERE c.plan_id = ? AND c.status = 'forming' GROUP BY c.id ORDER BY c.created_at LIMIT 1`,
      ).get(plan.id);
      return { ...plan, pot: potOf(plan), taken: open?.taken ?? 1 };
    });
  }

  function summarize(circle, member) {
    const taken = q("SELECT COUNT(*) AS n FROM circle_members WHERE circle_id = ?").get(circle.id).n;
    const outstanding = outstandingOf(circle.id, member.id);
    // Debt is only what the guarantee paid for; this month's share isn't late yet.
    const owed = outstanding.filter((i) => i.status === "covered").reduce((t, i) => t + i.amount, 0);
    const dueNow = outstanding.filter((i) => i.status === "due").reduce((t, i) => t + i.amount, 0);
    return {
      id: circle.id,
      planId: circle.plan_id,
      status: circle.status,
      size: circle.size,
      months: circle.months,
      share: circle.share,
      pot: circle.size * circle.share,
      currentMonth: circle.current_month,
      deadline: circle.deadline,
      taken,
      position: member.position,
      payMethod: member.pay_method,
      wonMonth: member.won_month,
      owed,
      dueNow,
    };
  }

  async function myCircles(phone) {
    await expireStale();
    return q(
      `SELECT c.*, m.id AS member_id FROM circle_members m JOIN circles c ON c.id = m.circle_id
       WHERE m.phone = ? AND c.status != 'expired' ORDER BY c.status = 'completed', c.created_at DESC`,
    )
      .all(phone)
      .map((row) => summarize(row, q("SELECT * FROM circle_members WHERE id = ?").get(row.member_id)));
  }

  // Members see each other only by seat number; phones never leave the server.
  async function circleView(phone, circleId, { ops = false } = {}) {
    await expireStale();
    const circle = getCircle(circleId);
    if (!circle) throw new HttpError(404, "این دوره پیدا نشد.");
    const members = membersOf(circleId);
    const me = members.find((m) => m.phone === phone);
    if (!me && !ops) throw new HttpError(404, "این دوره پیدا نشد.");

    const draws = q("SELECT * FROM circle_draws WHERE circle_id = ? ORDER BY month").all(circleId);
    const reveals = new Map(draws.filter((d) => d.kind === "lottery").map((d) => [d.draw_no, d.reveal]));
    const contributions = me
      ? q("SELECT month, amount, status, method, settled_at FROM contributions WHERE circle_id = ? AND member_id = ? ORDER BY month").all(
          circleId,
          me.id,
        )
      : [];

    return {
      circle: me ? summarize(circle, me) : { ...summarize(circle, members[0]), position: null, owed: 0, dueNow: 0 },
      anchor: circle.anchor,
      nonceDigest: circle.nonce_digest,
      members: members.map((m) => ({
        id: m.id,
        position: m.position,
        isOperator: Boolean(m.is_operator),
        isMe: m.id === me?.id,
        wonMonth: m.won_month,
        nonce: circle.status === "forming" ? null : m.nonce,
      })),
      draws: draws.map((d) => ({
        month: d.month,
        kind: d.kind,
        drawNo: d.draw_no,
        reveal: d.reveal,
        previous: d.kind === "lottery" ? (d.draw_no === 1 ? circle.anchor : reveals.get(d.draw_no - 1)) : null,
        seed: d.seed,
        eligible: JSON.parse(d.eligible),
        winner: d.winner_member_id,
        pot: d.pot,
        paidOut: Boolean(d.payout_ref),
        createdAt: d.created_at,
      })),
      contributions: contributions.map((c) => ({
        month: c.month,
        amount: c.amount,
        status: c.status === "covered" && c.settled_at ? "settled" : c.status,
        method: c.method,
      })),
    };
  }

  // ---------- ops / simulator ----------

  function listCircles() {
    return q(
      `SELECT c.*, (SELECT COUNT(*) FROM circle_members m WHERE m.circle_id = c.id) AS taken
       FROM circles c ORDER BY c.created_at DESC`,
    )
      .all()
      .map((c) => ({
        id: c.id,
        planId: c.plan_id,
        status: c.status,
        size: c.size,
        months: c.months,
        share: c.share,
        taken: c.taken,
        currentMonth: c.current_month,
      }));
  }

  // Seat simulated members so a demo circle can start. Every fourth bot
  // "forgets" to pay, which shows the guarantee at work.
  async function fillWithBots(circleId) {
    const circle = getCircle(circleId);
    if (!circle || circle.status !== "forming") throw new HttpError(400, "فقط دوره‌ی در حال تکمیل را می‌شود پر کرد.");
    transaction(db, () => {
      let taken = q("SELECT COUNT(*) AS n FROM circle_members WHERE circle_id = ?").get(circleId).n;
      while (taken < circle.size) {
        taken += 1;
        const failing = taken % 4 === 0;
        q(
          `INSERT INTO circle_members (id, circle_id, position, phone, is_bot, nonce, pay_method, mandate_id, joined_at)
           VALUES (?, ?, ?, NULL, 1, ?, 'auto', ?, ?)`,
        ).run(newId(), circleId, taken, randomHex(16), `sim-mandate-${failing ? "failing-" : ""}${newId()}`, now());
      }
      startCircle(circle);
    });
    await publishNonceDigest(circleId);
  }

  return {
    eligibility,
    join,
    leave,
    closeMonth,
    startCheckout,
    getCheckout,
    completeCheckout,
    planSummaries,
    myCircles,
    circleView,
    listCircles,
    fillWithBots,
  };
}
