import { test } from "node:test";
import assert from "node:assert/strict";
import { openDatabase } from "./db.js";
import { createCircleService } from "./circles.js";
import { createDigipaySimulator } from "./digipay/simulator.js";
import { verifyDraw } from "../src/lib/fairness.js";

// Phones ending 4–9 get a 25M monthly limit from the simulator's scoring.
const phone = (i) => `0912000${String(i).padStart(3, "0")}9`;

function setup() {
  const db = openDatabase(":memory:");
  const digipay = createDigipaySimulator();
  const payouts = [];
  const send = digipay.payouts.send;
  digipay.payouts.send = async (p) => {
    payouts.push(p);
    return send(p);
  };
  return { db, service: createCircleService({ db, digipay }), payouts };
}

async function fillPlan(service, planId, members, payMethod = () => "auto") {
  let circleId;
  for (let i = 1; i <= members; i++) {
    ({ circleId } = await service.join({ phone: phone(i), planId, payMethod: payMethod(i) }));
  }
  return circleId;
}

test("scoring gates who can join and how much they can commit", async () => {
  const { service } = setup();
  await assert.rejects(service.join({ phone: "09120000000", planId: "p12-5", payMethod: "auto" }), { status: 403 });
  // Limit 5M: the 5M plan fits, the 10M plan doesn't, and a second 5M plan doesn't either.
  await service.join({ phone: "09120000001", planId: "p12-5", payMethod: "auto" });
  await assert.rejects(service.join({ phone: "09120000001", planId: "p12-10", payMethod: "auto" }), { status: 403 });
  await assert.rejects(service.join({ phone: "09120000001", planId: "p12-5", payMethod: "auto" }), { status: 409 });
});

test("a circle starts when full, the operator takes month 1, and everyone receives exactly once", async () => {
  const { service, payouts } = setup();
  const circleId = await fillPlan(service, "p12-5", 11);

  let view = service.circleView(phone(1), circleId);
  assert.equal(view.circle.status, "active");
  assert.equal(view.members.length, 12);
  assert.ok(view.members[0].isOperator);
  assert.match(view.nonceDigest, /^[0-9a-f]{64}$/);

  for (let m = 1; m <= 12; m++) await service.closeMonth(circleId);

  view = service.circleView(phone(1), circleId);
  assert.equal(view.circle.status, "completed");
  assert.deepEqual(
    view.members.map((m) => m.wonMonth).sort((a, b) => a - b),
    Array.from({ length: 12 }, (_, i) => i + 1),
  );
  assert.equal(view.draws[0].kind, "operator");
  assert.equal(view.draws[11].kind, "last");
  assert.equal(view.draws.filter((d) => d.kind === "lottery").length, 10);
  assert.equal(payouts.length, 12);
  assert.ok(payouts.every((p) => p.amount === 60_000_000));
  assert.ok(payouts[0].operator);
});

test("every lottery can be verified by a member, and tampering is detected", async () => {
  const { service } = setup();
  const circleId = await fillPlan(service, "p12-5", 11);
  for (let m = 1; m <= 5; m++) await service.closeMonth(circleId);

  const view = service.circleView(phone(3), circleId);
  const lotteries = view.draws.filter((d) => d.kind === "lottery");
  assert.equal(lotteries.length, 4);
  for (const d of lotteries) {
    const result = await verifyDraw({ ...d, digest: view.nonceDigest });
    assert.ok(result.ok, `draw for month ${d.month} should verify`);
  }

  const [first] = lotteries;
  const forgedWinner = first.eligible.find((id) => id !== first.winner);
  assert.equal((await verifyDraw({ ...first, digest: view.nonceDigest, winner: forgedWinner })).ok, false);
  const forgedReveal = await verifyDraw({ ...first, digest: view.nonceDigest, reveal: "0".repeat(64) });
  assert.equal(forgedReveal.linkOk, false);
});

test("the guarantee covers unpaid shares, and debtors sit out the lottery until they pay", async () => {
  const { service } = setup();
  const debtor = phone(5);
  const circleId = await fillPlan(service, "p12-5", 11, (i) => (i === 5 ? "manual" : "auto"));

  await service.closeMonth(circleId); // month 1: debtor didn't pay
  let view = service.circleView(debtor, circleId);
  assert.equal(view.contributions[0].status, "covered");
  assert.equal(view.circle.owed, 5_000_000); // month 1, paid by the guarantee
  assert.equal(view.circle.dueNow, 5_000_000); // month 2, not late yet

  await service.closeMonth(circleId); // month 2: still unpaid
  view = service.circleView(debtor, circleId);
  const me = view.members.find((m) => m.isMe);
  assert.ok(!view.draws[1].eligible.includes(me.id), "a member who owes is left out of the draw");

  const { checkoutId } = await service.startCheckout({ phone: debtor, circleId });
  assert.equal(service.getCheckout(debtor, checkoutId).amount, 15_000_000);
  await service.completeCheckout({ phone: debtor, id: checkoutId, action: "pay" });
  view = service.circleView(debtor, circleId);
  assert.equal(view.circle.owed, 0);
  assert.deepEqual(view.contributions.map((c) => c.status), ["settled", "settled", "paid"]);
});

test("members only see seats, never each other's phones, and strangers see nothing", async () => {
  const { service } = setup();
  const circleId = await fillPlan(service, "p12-5", 11);
  const view = service.circleView(phone(2), circleId);
  assert.ok(!JSON.stringify(view).includes("09120"));
  assert.throws(() => service.circleView("09129999999", circleId), { status: 404 });
});

test("a month can't be closed twice at once", async () => {
  const { service } = setup();
  const circleId = await fillPlan(service, "p12-5", 11);
  const results = await Promise.allSettled([service.closeMonth(circleId), service.closeMonth(circleId)]);
  assert.equal(results.filter((r) => r.status === "fulfilled").length, 1);
  assert.equal(service.circleView(phone(1), circleId).circle.currentMonth, 2);
});

test("ops can fill a forming circle with simulated members to start it", async () => {
  const { service } = setup();
  const { circleId } = await service.join({ phone: phone(1), planId: "p24-10", payMethod: "auto" });
  await service.fillWithBots(circleId);
  const view = service.circleView(phone(1), circleId);
  assert.equal(view.circle.status, "active");
  assert.equal(view.members.length, 24);
  await service.closeMonth(circleId);
  await service.closeMonth(circleId);
  // Failing bots' month-1 shares were covered by the guarantee.
  assert.equal(service.circleView(phone(1), circleId).draws[1].pot, 240_000_000);
});
