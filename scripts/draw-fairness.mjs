// Runs the first lottery (month 2; month 1 always goes to Digi Gharz) of many
// separate 12-seat groups through the real service, tallies which seat won
// each time, and checks the tally against a fair draw with a chi-square test.
// Every draw is also re-verified the way a member's phone does it.
//
//   node scripts/draw-fairness.mjs [rounds=500]
import { testDatabase } from "../server/test-db.js";
import { createCircleService } from "../server/circles.js";
import { createDigipaySimulator } from "../server/digipay/simulator.js";
import { verifyDraw } from "../src/lib/fairness.js";

const ROUNDS = Number(process.argv[2]) || 500;
const db = await testDatabase();
const service = createCircleService({ db, digipay: createDigipaySimulator(), formTimeoutMs: 60 * 60 * 1000 });

const wins = new Map(); // seat position → wins
let entrants = 0;
let verified = 0;

for (let i = 0; i < ROUNDS; i++) {
  // A fresh member each round (phones ending in 9 can commit to this plan).
  const phone = `0913${String(i).padStart(6, "0")}9`;
  const { checkoutId } = await service.join({ phone, planId: "p12-5" });
  const { circleId } = await service.completeCheckout({ phone, id: checkoutId, action: "pay" });
  await service.fillWithBots(circleId);
  // The simulator makes every fourth bot "forget" to pay (to demo the
  // guarantee), which rightly keeps it out of the draw. Here everyone pays,
  // so every seat has the same chance and any bias would show.
  await db.run(
    "UPDATE circle_members SET mandate_id = 'sim-mandate-' || id WHERE circle_id = ? AND mandate_id LIKE 'sim-mandate-failing-%'",
    circleId,
  );
  // The member pays month 2 so everyone is in the draw (bots pay by themselves).
  const due = await service.startCheckout({ phone, circleId }).catch(() => null);
  if (due) await service.completeCheckout({ phone, id: due.checkoutId, action: "pay" });
  await service.closeMonth(circleId);

  const view = await service.circleView(phone, circleId);
  const draw = view.draws.find((d) => d.month === 2);
  const winner = view.members.find((m) => m.id === draw.winner);
  wins.set(winner.position, (wins.get(winner.position) ?? 0) + 1);
  entrants = draw.eligible.length;
  if ((await verifyDraw({ ...draw, digest: view.nonceDigest })).ok) verified++;
}

// Chi-square goodness of fit against "every seat equally likely".
const seats = [...wins.keys()]
  .concat(Array.from({ length: 11 }, (_, k) => k + 2))
  .filter((v, k, a) => a.indexOf(v) === k);
seats.sort((a, b) => a - b);
const expected = ROUNDS / seats.length;
const chi2 = seats.reduce((t, s) => t + ((wins.get(s) ?? 0) - expected) ** 2 / expected, 0);
const df = seats.length - 1;
// Critical value at p = 0.05 for 10 degrees of freedom.
const critical = { 10: 18.307 }[df];

console.log(`draws: ${ROUNDS}, entrants per draw: ${entrants}, verified: ${verified}/${ROUNDS}`);
console.log(`expected wins per seat: ${expected.toFixed(1)}`);
const most = Math.max(...seats.map((s) => wins.get(s) ?? 0));
for (const s of seats) {
  const n = wins.get(s) ?? 0;
  console.log(`seat ${String(s).padStart(2)}: ${String(n).padStart(4)}  ${"█".repeat(Math.round((n / most) * 40))}`);
}
console.log(`chi-square: ${chi2.toFixed(2)} (df ${df}; bias would show above ${critical ?? "?"} at p=0.05)`);

// The pick itself, on its own and many more times: random reveals and nonce
// digests, 11 entrants, which index wins.
const { pickWinner, randomHex, sha256Hex } = await import("../src/lib/fairness.js");
const PICKS = 100_000;
const byIndex = Array(11).fill(0);
const ids = Array.from({ length: 11 }, (_, k) => `m${String(k).padStart(2, "0")}`);
for (let i = 0; i < PICKS; i++) {
  const { winner } = await pickWinner({
    reveal: randomHex(),
    digest: await sha256Hex(randomHex()),
    month: 2,
    eligible: ids,
  });
  byIndex[ids.indexOf(winner)]++;
}
const e2 = PICKS / 11;
const chi2b = byIndex.reduce((t, n) => t + (n - e2) ** 2 / e2, 0);
console.log(
  `\npick function alone, ${PICKS} times: ${byIndex.map((n) => ((n / PICKS) * 100).toFixed(2) + "%").join(" ")}`,
);
console.log(`chi-square: ${chi2b.toFixed(2)} (df 10; bias would show above 18.307 at p=0.05)`);
