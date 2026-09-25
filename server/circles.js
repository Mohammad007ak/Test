// Guaranteed circles: the paid product, with Digipay as operator.
// The calendar (due dates, five payment days, draw on the sixth) lives in
// src/lib/schedule.js.
//
// A circle runs one plan. It fills up while "forming", then runs one month
// per cycle. Each month every member owes one share and one member receives
// the pot (size × share):
//   month 1      → the operator (position 1), always;
//   last month   → whoever hasn't received yet;
//   other months → a provably fair lottery among members who haven't
//                  received yet and don't owe anything.
// Installments are collected at the start of each month and paid straight
// out to that month's recipient. Month 1 is everyone's first share, paid on
// joining; it goes to the operator the moment the circle starts. Members
// pay later months through the cash gateway. Whatever is still unpaid
// when the month closes (the draw, on the sixth day) is debited from their Digipay wallet (they agree to
// this in the terms); if the wallet can't cover it, the operator pays in
// their place ("covered") so the pot is always whole, and the member owes it.
//
// Joining costs the first share up front: the member pays it through the
// gateway and only then takes a seat. A forming circle waits for members
// until its deadline; if it doesn't fill in time it expires, everyone in it
// is released and their first share is refunded (as it is when someone
// leaves the queue).

import { HttpError } from "./errors.js";
import { planById, PLANS, potOf } from "../src/lib/plans.js";
import { buildChain, nonceDigest, pickWinner, randomHex } from "../src/lib/fairness.js";
import { newId } from "../src/lib/fund.js";
import { drawAt } from "../src/lib/schedule.js";

const NONCE = /^[0-9a-f]{32,64}$/;

const HOUR = 60 * 60 * 1000;

// Every query takes a handle `d`: the database, or a transaction inside
// db.transaction(). Inside a transaction only its own queries are awaited.
export function createCircleService({ db, digipay, now = Date.now, formTimeoutMs = HOUR }) {
  const getCircle = (id, d = db) => d.get("SELECT * FROM circles WHERE id = ?", id);
  const membersOf = (circleId, d = db) =>
    d.all("SELECT * FROM circle_members WHERE circle_id = ? ORDER BY position", circleId);
  // In a Postgres transaction, lock the circle row so two joins can't both
  // take the last seat. SQLite transactions already run one at a time.
  const lockCircle = (tx, id) =>
    tx.get(`SELECT * FROM circles WHERE id = ?${tx.kind === "postgres" ? " FOR UPDATE" : ""}`, id);
  const countMembers = async (circleId, d = db) =>
    (await d.get("SELECT COUNT(*) AS n FROM circle_members WHERE circle_id = ?", circleId)).n;

  // The audit trail behind the operator's reports: one row per money
  // movement or lifecycle step.
  const log = (d, kind, { circleId = null, memberId = null, phone = null, amount = null, detail = null } = {}) =>
    d.run(
      "INSERT INTO ops_events (id, at, kind, circle_id, member_id, phone, amount, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
      newId(),
      now(),
      kind,
      circleId,
      memberId,
      phone,
      amount,
      detail === null ? null : JSON.stringify(detail),
    );

  // ---------- forming ----------

  async function createCircle(plan) {
    const secret = randomHex();
    const [anchor] = await buildChain(secret, plan.months);
    const id = newId();
    await db.transaction(async (tx) => {
      await tx.run(
        `INSERT INTO circles (id, plan_id, status, size, months, share, chain_secret, anchor, created_at, deadline)
         VALUES (?, ?, 'forming', ?, ?, ?, ?, ?, ?, ?)`,
        id,
        plan.id,
        plan.size,
        plan.months,
        plan.share,
        secret,
        anchor,
        now(),
        now() + formTimeoutMs,
      );
      await tx.run(
        `INSERT INTO circle_members (id, circle_id, position, phone, is_operator, nonce, pay_method, joined_at)
         VALUES (?, ?, 1, NULL, 1, ?, 'operator', ?)`,
        newId(),
        id,
        randomHex(16),
        now(),
      );
      await log(tx, "circle_created", { circleId: id, detail: { planId: plan.id } });
    });
    return id;
  }

  async function openCircleFor(plan) {
    const open = await db.get(
      "SELECT id FROM circles WHERE plan_id = ? AND status = 'forming' AND deadline > ? ORDER BY created_at LIMIT 1",
      plan.id,
      now(),
    );
    return open?.id ?? createCircle(plan);
  }

  // Release everyone from circles that didn't fill before their deadline.
  async function expireStale() {
    const stale = await db.all("SELECT id FROM circles WHERE status = 'forming' AND deadline <= ?", now());
    for (const { id } of stale) {
      const { changes } = await db.run("UPDATE circles SET status = 'expired' WHERE id = ? AND status = 'forming'", id);
      if (!changes) continue;
      const circle = await getCircle(id);
      const members = await membersOf(id);
      await log(db, "circle_expired", { circleId: id, detail: { taken: members.length, size: circle.size } });
      for (const m of members) await release(m, circle);
    }
  }

  // Undo what a seat holds: the wallet mandate and the prepaid first share.
  async function release(member, circle) {
    if (member.mandate_id) await digipay.payments.revokeMandate({ mandateId: member.mandate_id });
    if (member.entry_ref && !member.is_bot) {
      await digipay.payments.refund({
        paymentRef: member.entry_ref,
        amount: circle.share,
      });
      await log(db, "refund", {
        circleId: circle.id,
        memberId: member.id,
        phone: member.phone,
        amount: circle.share,
        detail: { reason: circle.status === "expired" ? "expired" : "left" },
      });
    }
  }

  async function openMonth(tx, circleId, month, share) {
    for (const m of await membersOf(circleId, tx)) {
      // Month 1 was paid on joining.
      const method = m.is_operator ? "operator" : month === 1 && m.entry_ref ? "entry" : null;
      await tx.run(
        `INSERT INTO contributions (circle_id, member_id, month, amount, status, method, ref, paid_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        circleId,
        m.id,
        month,
        share,
        method ? "paid" : "due",
        method,
        method === "entry" ? m.entry_ref : null,
        method ? now() : null,
      );
    }
  }

  // Runs inside the transaction that takes the last seat.
  async function startCircle(tx, circle) {
    await tx.run(
      "UPDATE circles SET status = 'active', started_at = ?, current_month = 1 WHERE id = ?",
      now(),
      circle.id,
    );
    await openMonth(tx, circle.id, 1, circle.share);
    await log(tx, "circle_started", { circleId: circle.id, detail: { fillMs: now() - circle.created_at } });
  }

  async function publishNonceDigest(circleId) {
    const circle = await getCircle(circleId);
    if (circle.status === "forming" || circle.nonce_digest) return;
    const digest = await nonceDigest((await membersOf(circleId)).map((m) => m.nonce));
    await db.run("UPDATE circles SET nonce_digest = ? WHERE id = ? AND nonce_digest IS NULL", digest, circleId);
  }

  async function committedMonthly(phone) {
    const row = await db.get(
      `SELECT COALESCE(SUM(c.share), 0) AS total FROM circle_members m JOIN circles c ON c.id = m.circle_id
       WHERE m.phone = ? AND c.status IN ('forming', 'active')`,
      phone,
    );
    return row.total;
  }

  async function eligibility(phone) {
    const score = await digipay.scoring.check(phone);
    const committed = await committedMonthly(phone);
    return {
      approved: Boolean(score.approved),
      monthlyLimit: score.monthlyLimit,
      committed,
      available: Math.max(0, score.monthlyLimit - committed),
    };
  }

  const seatIn = (phone, planId) =>
    db.get(
      `SELECT m.circle_id FROM circle_members m JOIN circles c ON c.id = m.circle_id
       WHERE m.phone = ? AND c.plan_id = ? AND c.status IN ('forming', 'active')`,
      phone,
      planId,
    );

  // Step 1 of joining: check the member can join, then send them to the
  // gateway to pay the first share. The seat is taken in completeCheckout.
  async function join({ phone, planId, nonce }) {
    const plan = planById(planId);
    if (!plan) throw new HttpError(404, "این طرح پیدا نشد.");
    await expireStale();
    if (await seatIn(phone, plan.id)) throw new HttpError(409, "شما در یک دوره‌ی فعال از همین طرح عضو هستید.");

    const e = await eligibility(phone);
    if (!e.approved) throw new HttpError(403, "در حال حاضر امکان عضویت در طرح‌ها برای شما فعال نیست.");
    if (e.available < plan.share) {
      throw new HttpError(403, "سقف اعتبار ماهانه‌ی شما برای این طرح کافی نیست. طرح کوچک‌تری را امتحان کنید.");
    }

    // A nonce from the member's own device: entropy the server couldn't know
    // when it committed to the hash chain.
    const memberNonce = NONCE.test(nonce ?? "") ? nonce : randomHex(16);
    const id = newId();
    const checkout = await digipay.payments.createCheckout({
      phone,
      amount: plan.share,
      ref: id,
    });
    await db.run(
      `INSERT INTO checkouts (id, kind, phone, plan_id, nonce, items, amount, status, ref, created_at)
       VALUES (?, 'entry', ?, ?, ?, '[1]', ?, 'pending', ?, ?)`,
      id,
      phone,
      plan.id,
      memberNonce,
      plan.share,
      checkout.checkoutRef,
      now(),
    );
    return { checkoutId: id, redirectUrl: checkout.url ?? null };
  }

  // Step 2, once the first share is paid: take a seat in the plan's open
  // circle (a fresh one if none is open).
  async function seat({ phone, plan, nonce, entryRef }) {
    // The wallet-debit fallback the member agrees to in the terms.
    const mandate = await digipay.payments.createMandate({
      phone,
      monthlyAmount: plan.share,
      months: plan.months,
    });

    for (let attempt = 0; attempt < 5; attempt++) {
      const circleId = await openCircleFor(plan);
      const joined = await db.transaction(async (tx) => {
        const circle = await lockCircle(tx, circleId);
        const taken = await countMembers(circleId, tx);
        if (circle.status !== "forming" || taken >= circle.size) return null;
        const memberId = newId();
        await tx.run(
          `INSERT INTO circle_members (id, circle_id, position, phone, nonce, pay_method, mandate_id, entry_ref, joined_at)
           VALUES (?, ?, ?, ?, ?, 'manual', ?, ?, ?)`,
          memberId,
          circleId,
          taken + 1,
          phone,
          nonce,
          mandate.mandateId,
          entryRef,
          now(),
        );
        await log(tx, "joined", { circleId, memberId, phone, amount: plan.share, detail: { position: taken + 1 } });
        if (taken + 1 === circle.size) await startCircle(tx, circle);
        return { circleId, memberId };
      });
      if (joined) {
        await publishNonceDigest(joined.circleId);
        await runDueDraws(joined.circleId); // pays month 1 out if this seat started it
        return joined;
      }
    }
    throw new HttpError(503, "لطفاً دوباره تلاش کنید.");
  }

  // Leaving is only possible while waiting for the circle to fill. Seats
  // behind the leaver move up so positions stay 1..n.
  async function leave({ phone, circleId }) {
    const member = await memberFor(phone, circleId);
    const left = await db.transaction(async (tx) => {
      if ((await lockCircle(tx, circleId)).status !== "forming") return false;
      await tx.run("DELETE FROM circle_members WHERE id = ?", member.id);
      await tx.run(
        "UPDATE circle_members SET position = -position WHERE circle_id = ? AND position > ?",
        circleId,
        member.position,
      );
      await tx.run("UPDATE circle_members SET position = -position - 1 WHERE circle_id = ? AND position < 0", circleId);
      return true;
    });
    if (!left) throw new HttpError(400, "گروه شروع شده و دیگر نمی‌شود از آن خارج شد.");
    await log(db, "left", { circleId, memberId: member.id, phone });
    await release(member, await getCircle(circleId));
  }

  // ---------- running ----------

  // Run every draw whose day has come (month 1's on the start day itself).
  // Called on a timer and whenever a circle is looked at, so nothing
  // depends on the timer alone. A failure is logged and retried next time.
  async function runDueDraws(circleId) {
    const circles = circleId
      ? [await getCircle(circleId)].filter(Boolean)
      : await db.all("SELECT * FROM circles WHERE status = 'active' AND closing = 0");
    for (let circle of circles) {
      while (
        circle.status === "active" &&
        !circle.closing &&
        now() >= drawAt(circle.started_at, circle.current_month)
      ) {
        try {
          await closeMonth(circle.id);
        } catch (error) {
          if (error.status !== 409) console.error(`draw for circle ${circle.id} failed:`, error.message);
          break;
        }
        circle = await getCircle(circle.id);
      }
    }
  }

  async function closeMonth(circleId) {
    const { changes: claimed } = await db.run(
      "UPDATE circles SET closing = 1 WHERE id = ? AND status = 'active' AND closing = 0",
      circleId,
    );
    if (!claimed) throw new HttpError(409, "این دوره فعال نیست یا در حال پردازش است.");

    try {
      await publishNonceDigest(circleId);
      const circle = await getCircle(circleId);
      const month = circle.current_month;
      const members = await membersOf(circleId);

      // 1. Debit the wallet of anyone who hasn't paid through the gateway.
      const due = await db.all(
        "SELECT * FROM contributions WHERE circle_id = ? AND month = ? AND status = 'due'",
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
          await db.run(
            `UPDATE contributions SET status = 'paid', method = 'wallet', ref = ?, paid_at = ?
             WHERE circle_id = ? AND member_id = ? AND month = ? AND status = 'due'`,
            charge.ref,
            now(),
            circleId,
            member.id,
            month,
          );
          await log(db, "wallet_debit", {
            circleId,
            memberId: member.id,
            phone: member.phone,
            amount: d.amount,
            detail: { month },
          });
        } else {
          await log(db, "wallet_failed", {
            circleId,
            memberId: member.id,
            phone: member.phone,
            amount: d.amount,
            detail: { month, reason: charge.reason ?? null },
          });
        }
      }

      // 2. Pick this month's recipient.
      const waiting = members.filter((m) => m.won_month === null);
      let draw;
      if (month === 1) {
        const operator = members.find((m) => m.is_operator);
        draw = {
          kind: "operator",
          winner: operator.id,
          eligible: [operator.id],
        };
      } else if (waiting.length === 1) {
        draw = {
          kind: "last",
          winner: waiting[0].id,
          eligible: [waiting[0].id],
        };
      } else {
        const owing = new Set(
          (
            await db.all(
              `SELECT DISTINCT member_id FROM contributions WHERE circle_id = ?
               AND ((status = 'covered' AND settled_at IS NULL) OR (month = ? AND status = 'due'))`,
              circleId,
              month,
            )
          ).map((r) => r.member_id),
        );
        let eligible = waiting.filter((m) => !owing.has(m.id)).map((m) => m.id);
        if (eligible.length === 0) eligible = waiting.map((m) => m.id);
        const drawNo =
          (await db.get("SELECT COUNT(*) AS n FROM circle_draws WHERE circle_id = ? AND kind = 'lottery'", circleId))
            .n + 1;
        const chain = await buildChain(circle.chain_secret, circle.months);
        const reveal = chain[drawNo];
        const { seed, winner } = await pickWinner({
          reveal,
          digest: (await getCircle(circleId)).nonce_digest,
          month,
          eligible,
        });
        draw = { kind: "lottery", drawNo, reveal, seed, winner, eligible };
      }

      // 3. Record it: the guarantee covers anyone still unpaid.
      const pot = circle.size * circle.share;
      await db.transaction(async (tx) => {
        const uncovered = await tx.all(
          "SELECT member_id, amount FROM contributions WHERE circle_id = ? AND month = ? AND status = 'due'",
          circleId,
          month,
        );
        await tx.run(
          `UPDATE contributions SET status = 'covered', method = 'guarantee', paid_at = ?
           WHERE circle_id = ? AND month = ? AND status = 'due'`,
          now(),
          circleId,
          month,
        );
        for (const u of uncovered) {
          const m = members.find((x) => x.id === u.member_id);
          await log(tx, "guarantee", {
            circleId,
            memberId: u.member_id,
            phone: m?.phone ?? null,
            amount: u.amount,
            detail: { month },
          });
        }
        await tx.run(
          `INSERT INTO circle_draws (circle_id, month, kind, draw_no, reveal, seed, eligible, winner_member_id, pot, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
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
        await tx.run("UPDATE circle_members SET won_month = ? WHERE id = ?", month, draw.winner);
        const winner = members.find((m) => m.id === draw.winner);
        await log(tx, "draw", {
          circleId,
          memberId: draw.winner,
          phone: winner.phone,
          amount: pot,
          detail: { month, kind: draw.kind, eligible: draw.eligible.length, position: winner.position },
        });
        if (month === circle.months) {
          await tx.run("UPDATE circles SET status = 'completed', closing = 0 WHERE id = ?", circleId);
        } else {
          await tx.run("UPDATE circles SET current_month = ?, closing = 0 WHERE id = ?", month + 1, circleId);
          await openMonth(tx, circleId, month + 1, circle.share);
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
      await db.run(
        "UPDATE circle_draws SET payout_ref = ? WHERE circle_id = ? AND month = ?",
        payout.ref,
        circleId,
        month,
      );
      await log(db, "payout", {
        circleId,
        memberId: recipient.id,
        phone: recipient.phone,
        amount: pot,
        detail: { month, operator: Boolean(recipient.is_operator), ref: payout.ref },
      });
      return { month, kind: draw.kind, winner: draw.winner, pot };
    } catch (error) {
      await db.run("UPDATE circles SET closing = 0 WHERE id = ?", circleId);
      throw error;
    }
  }

  // ---------- manual payments ----------

  async function memberFor(phone, circleId) {
    const member = await db.get("SELECT * FROM circle_members WHERE circle_id = ? AND phone = ?", circleId, phone);
    if (!member) throw new HttpError(404, "این دوره پیدا نشد.");
    return member;
  }

  const outstandingOf = (circleId, memberId) =>
    db.all(
      `SELECT month, amount, status FROM contributions WHERE circle_id = ? AND member_id = ?
       AND (status = 'due' OR (status = 'covered' AND settled_at IS NULL)) ORDER BY month`,
      circleId,
      memberId,
    );

  async function startCheckout({ phone, circleId }) {
    const member = await memberFor(phone, circleId);
    const items = await outstandingOf(circleId, member.id);
    if (items.length === 0) throw new HttpError(400, "پرداخت معوقی ندارید.");
    const amount = items.reduce((t, i) => t + i.amount, 0);
    const id = newId();
    const checkout = await digipay.payments.createCheckout({
      phone,
      amount,
      ref: id,
    });
    await db.run(
      `INSERT INTO checkouts (id, kind, phone, plan_id, circle_id, member_id, items, amount, status, ref, created_at)
       VALUES (?, 'dues', ?, ?, ?, ?, ?, ?, 'pending', ?, ?)`,
      id,
      phone,
      (await getCircle(circleId)).plan_id,
      circleId,
      member.id,
      JSON.stringify(items.map((i) => i.month)),
      amount,
      checkout.checkoutRef,
      now(),
    );
    return { checkoutId: id, redirectUrl: checkout.url ?? null };
  }

  async function getCheckout(phone, id) {
    const checkout = await db.get("SELECT * FROM checkouts WHERE id = ? AND phone = ?", id, phone);
    if (!checkout) throw new HttpError(404, "پرداخت پیدا نشد.");
    return {
      id: checkout.id,
      kind: checkout.kind,
      amount: checkout.amount,
      status: checkout.status,
      months: JSON.parse(checkout.items),
      circleId: checkout.circle_id,
      planId: checkout.plan_id,
    };
  }

  async function completeCheckout({ phone, id, action }) {
    const checkout = await db.get("SELECT * FROM checkouts WHERE id = ? AND phone = ?", id, phone);
    if (!checkout) throw new HttpError(404, "پرداخت پیدا نشد.");
    if (checkout.status !== "pending") throw new HttpError(400, "این پرداخت قبلاً نهایی شده است.");
    const result = await digipay.payments.verifyCheckout({
      checkoutRef: checkout.ref,
      action,
    });
    if (checkout.kind === "entry") return completeEntry(checkout, result);
    await db.transaction(async (tx) => {
      const { changes } = await tx.run(
        "UPDATE checkouts SET status = ?, ref = ? WHERE id = ? AND status = 'pending'",
        result.ok ? "paid" : "cancelled",
        result.ref ?? checkout.ref,
        id,
      );
      if (!changes) throw new HttpError(400, "این پرداخت قبلاً نهایی شده است.");
      if (!result.ok) return;
      let paid = 0;
      let settled = 0;
      for (const month of JSON.parse(checkout.items)) {
        const args = [checkout.circle_id, checkout.member_id, month];
        const row = await tx.get(
          "SELECT amount, status, settled_at FROM contributions WHERE circle_id = ? AND member_id = ? AND month = ?",
          ...args,
        );
        await tx.run(
          `UPDATE contributions SET status = 'paid', method = 'manual', ref = ?, paid_at = ?
           WHERE circle_id = ? AND member_id = ? AND month = ? AND status = 'due'`,
          result.ref,
          now(),
          ...args,
        );
        await tx.run(
          `UPDATE contributions SET settled_at = ?
           WHERE circle_id = ? AND member_id = ? AND month = ? AND status = 'covered' AND settled_at IS NULL`,
          now(),
          ...args,
        );
        if (row?.status === "due") paid += row.amount;
        if (row?.status === "covered" && !row.settled_at) settled += row.amount;
      }
      const who = { circleId: checkout.circle_id, memberId: checkout.member_id, phone: checkout.phone };
      if (paid) await log(tx, "gateway_payment", { ...who, amount: paid });
      if (settled) await log(tx, "debt_settled", { ...who, amount: settled });
    });
    return { ok: result.ok, circleId: checkout.circle_id };
  }

  async function completeEntry(checkout, result) {
    const { changes: claimed } = await db.run(
      "UPDATE checkouts SET status = ?, ref = ? WHERE id = ? AND status = 'pending'",
      result.ok ? "paid" : "cancelled",
      result.ref ?? checkout.ref,
      checkout.id,
    );
    if (!claimed) throw new HttpError(400, "این پرداخت قبلاً نهایی شده است.");
    if (!result.ok) return { ok: false, circleId: null };

    const plan = planById(checkout.plan_id);
    await expireStale();
    // Paid twice for the same plan (two tabs): keep the seat, return the money.
    const existing = await seatIn(checkout.phone, plan.id);
    if (existing) {
      await digipay.payments.refund({
        paymentRef: result.ref,
        amount: checkout.amount,
      });
      await db.run("UPDATE checkouts SET status = 'refunded' WHERE id = ?", checkout.id);
      await log(db, "refund", {
        circleId: existing.circle_id,
        phone: checkout.phone,
        amount: checkout.amount,
        detail: { reason: "duplicate" },
      });
      return { ok: true, refunded: true, circleId: existing.circle_id };
    }
    const { circleId, memberId } = await seat({
      phone: checkout.phone,
      plan,
      nonce: checkout.nonce,
      entryRef: result.ref,
    });
    await db.run("UPDATE checkouts SET circle_id = ?, member_id = ? WHERE id = ?", circleId, memberId, checkout.id);
    return { ok: true, circleId };
  }

  // ---------- views ----------

  async function planSummaries() {
    await expireStale();
    const summaries = [];
    for (const plan of PLANS) {
      const open = await db.get(
        `SELECT c.id, COUNT(m.id) AS taken FROM circles c JOIN circle_members m ON m.circle_id = c.id
         WHERE c.plan_id = ? AND c.status = 'forming' GROUP BY c.id, c.created_at ORDER BY c.created_at LIMIT 1`,
        plan.id,
      );
      summaries.push({ ...plan, pot: potOf(plan), taken: open?.taken ?? 1 });
    }
    return summaries;
  }

  // The reveal animation plays once per draw; this records that it did.
  async function markSeen({ phone, circleId, month }) {
    const member = await memberFor(phone, circleId);
    const latest = (await db.get("SELECT MAX(month) AS m FROM circle_draws WHERE circle_id = ?", circleId)).m ?? 1;
    const seen = Math.min(Math.max(Number(month) || 1, member.seen_month), latest);
    await db.run("UPDATE circle_members SET seen_month = ? WHERE id = ?", seen, member.id);
  }

  async function summarize(circle, member) {
    const taken = await countMembers(circle.id);
    const outstanding = await outstandingOf(circle.id, member.id);
    // Debt is only what the guarantee paid for; this month's share isn't late yet.
    const owed = outstanding.filter((i) => i.status === "covered").reduce((t, i) => t + i.amount, 0);
    const dueNow = outstanding.filter((i) => i.status === "due").reduce((t, i) => t + i.amount, 0);
    // How many seats have been paid their pot so far (Digipay's month 1 included).
    const { n: received } = await db.get(
      "SELECT COUNT(*) AS n FROM circle_draws WHERE circle_id = ? AND payout_ref IS NOT NULL",
      circle.id,
    );
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
      startedAt: circle.started_at,
      seenMonth: member.seen_month,
      taken,
      position: member.position,
      payMethod: member.pay_method,
      wonMonth: member.won_month,
      received,
      owed,
      dueNow,
    };
  }

  async function myCircles(phone) {
    await expireStale();
    await runDueDraws();
    const rows = await db.all(
      `SELECT c.*, m.id AS member_id FROM circle_members m JOIN circles c ON c.id = m.circle_id
       WHERE m.phone = ? AND c.status != 'expired' ORDER BY c.status = 'completed', c.created_at DESC`,
      phone,
    );
    const result = [];
    for (const row of rows) {
      result.push(await summarize(row, await db.get("SELECT * FROM circle_members WHERE id = ?", row.member_id)));
    }
    return result;
  }

  // Members see each other only by seat number; phones never leave the server.
  async function circleView(phone, circleId, { ops = false } = {}) {
    await expireStale();
    await runDueDraws(circleId);
    const circle = await getCircle(circleId);
    if (!circle) throw new HttpError(404, "این دوره پیدا نشد.");
    const members = await membersOf(circleId);
    const me = members.find((m) => m.phone === phone);
    if (!me && !ops) throw new HttpError(404, "این دوره پیدا نشد.");

    const draws = await db.all("SELECT * FROM circle_draws WHERE circle_id = ? ORDER BY month", circleId);
    const reveals = new Map(draws.filter((d) => d.kind === "lottery").map((d) => [d.draw_no, d.reveal]));
    const contributions = me
      ? await db.all(
          "SELECT month, amount, status, method, settled_at FROM contributions WHERE circle_id = ? AND member_id = ? ORDER BY month",
          circleId,
          me.id,
        )
      : [];

    return {
      circle: me
        ? await summarize(circle, me)
        : {
            ...(await summarize(circle, members[0])),
            position: null,
            owed: 0,
            dueNow: 0,
          },
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

  // Seat simulated members so a demo circle can start. Every fourth bot
  // "forgets" to pay, which shows the guarantee at work.
  async function fillWithBots(circleId) {
    const filled = await db.transaction(async (tx) => {
      const circle = await lockCircle(tx, circleId);
      if (!circle || circle.status !== "forming") return false;
      let taken = await countMembers(circleId, tx);
      while (taken < circle.size) {
        taken += 1;
        const failing = taken % 4 === 0;
        await tx.run(
          `INSERT INTO circle_members (id, circle_id, position, phone, is_bot, nonce, pay_method, mandate_id, entry_ref, joined_at)
           VALUES (?, ?, ?, NULL, 1, ?, 'auto', ?, ?, ?)`,
          newId(),
          circleId,
          taken,
          randomHex(16),
          `sim-mandate-${failing ? "failing-" : ""}${newId()}`,
          `sim-entry-${newId()}`,
          now(),
        );
      }
      await startCircle(tx, circle);
      return true;
    });
    if (!filled) throw new HttpError(400, "فقط دوره‌ی در حال تکمیل را می‌شود پر کرد.");
    await publishNonceDigest(circleId);
    await runDueDraws(circleId);
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
    fillWithBots,
    runDueDraws,
    markSeen,
  };
}
