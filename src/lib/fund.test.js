import { test } from "node:test";
import assert from "node:assert/strict";
import { addMonths, monthsBetween, toJalali } from "./jalali.js";
import {
  createLoan,
  fundBalance,
  installmentAmount,
  listDues,
  loanProgress,
  lotteryEntries,
  overdueDues,
  pickWinner,
} from "./fund.js";

const fund = {
  name: "صندوق تست",
  contribution: 1_000_000,
  loanAmount: 10_000_000,
  installments: 3,
  startMonth: "1405-01",
  cycle: 1,
};

function makeState() {
  return {
    version: 1,
    fund,
    members: [
      { id: "a", name: "علی", phone: "", shares: 1, joinMonth: "1405-01" },
      { id: "b", name: "سارا", phone: "", shares: 2, joinMonth: "1405-02" },
    ],
    payments: [],
    loans: [],
  };
}

test("jalali month arithmetic wraps across years", () => {
  assert.equal(addMonths("1404-11", 3), "1405-02");
  assert.equal(addMonths("1405-01", -1), "1404-12");
  assert.deepEqual(monthsBetween("1404-12", "1405-02"), ["1404-12", "1405-01", "1405-02"]);
});

test("converts a gregorian date to jalali", () => {
  assert.deepEqual(toJalali(new Date("2026-03-21T12:00:00Z")), { year: 1405, month: 1, day: 1 });
});

test("contribution dues start at each member's join month and scale by shares", () => {
  const dues = listDues(makeState(), "1405-03");
  const ali = dues.filter((d) => d.memberId === "a");
  const sara = dues.filter((d) => d.memberId === "b");
  assert.equal(ali.length, 3);
  assert.equal(sara.length, 2);
  assert.equal(sara[0].amount, 2_000_000);
});

test("installments split evenly with the remainder on the last one", () => {
  const loan = { amount: 10_000_000, installments: 3 };
  const parts = [0, 1, 2].map((i) => installmentAmount(loan, i));
  assert.deepEqual(parts, [3_333_333, 3_333_333, 3_333_334]);
});

test("payments mark dues as paid and feed the balance", () => {
  const state = makeState();
  state.payments.push({ id: "p1", memberId: "a", type: "contribution", month: "1405-01", amount: 1_000_000 });
  const overdue = overdueDues(state, "1405-03");
  assert.equal(overdue.filter((d) => d.memberId === "a").length, 1);
  assert.equal(fundBalance(state), 1_000_000);
});

test("loans create installment dues from the month after the draw", () => {
  const state = makeState();
  const loan = createLoan(fund, "a", "1405-02");
  state.loans.push(loan);
  const installments = listDues(state, "1405-12").filter((d) => d.type === "installment");
  assert.deepEqual(
    installments.map((d) => d.month),
    ["1405-03", "1405-04", "1405-05"],
  );
  assert.equal(fundBalance(state), -10_000_000);

  state.payments.push({
    id: "p",
    memberId: "a",
    type: "installment",
    loanId: loan.id,
    month: "1405-03",
    amount: 3_333_333,
  });
  assert.deepEqual(loanProgress(state, loan), {
    paidCount: 1,
    paidAmount: 3_333_333,
    remaining: 6_666_667,
    done: false,
  });
});

test("lottery tickets follow shares and are used up by wins", () => {
  const state = makeState();
  assert.deepEqual(
    lotteryEntries(state).map((e) => e.tickets),
    [1, 2],
  );
  state.loans.push(createLoan(fund, "b", "1405-02"));
  assert.deepEqual(
    lotteryEntries(state).map((e) => [e.member.id, e.tickets]),
    [
      ["a", 1],
      ["b", 1],
    ],
  );
});

test("pickWinner is weighted by tickets", () => {
  const entries = [
    { member: { id: "a" }, tickets: 1 },
    { member: { id: "b" }, tickets: 2 },
  ];
  assert.equal(pickWinner(entries, () => 0).id, "a");
  assert.equal(pickWinner(entries, () => 0.4).id, "b");
  assert.equal(pickWinner(entries, () => 0.99).id, "b");
  assert.equal(
    pickWinner([], () => 0),
    null,
  );
});
