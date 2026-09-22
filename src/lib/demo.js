import { addMonths, currentMonthKey, monthsBetween } from "./jalali.js";
import { createLoan, installmentAmount, newId } from "./fund.js";

const NAMES = [
  ["مریم احمدی", 1],
  ["رضا کریمی", 2],
  ["زهرا حسینی", 1],
  ["علی محمدی", 1],
  ["فاطمه رضایی", 1],
  ["حسین موسوی", 2],
  ["نرگس جعفری", 1],
  ["امیر صادقی", 1],
];

// A fund that started six months ago, with a couple of loans and some
// members who are behind, so every screen has something to show.
export function createDemoState() {
  const now = currentMonthKey();
  const startMonth = addMonths(now, -6);
  const fund = {
    name: "صندوق خانوادگی مهر",
    contribution: 2_000_000,
    loanAmount: 30_000_000,
    installments: 10,
    startMonth,
    cycle: 1,
  };

  const members = NAMES.map(([name, shares], i) => ({
    id: newId() + i,
    name,
    phone: `0912${String(1000000 + i * 111111).slice(0, 7)}`,
    shares,
    joinMonth: startMonth,
  }));

  const lateMembers = new Set([members[2].id, members[6].id]);
  const payments = [];
  for (const month of monthsBetween(startMonth, now)) {
    for (const member of members) {
      const isRecent = month >= addMonths(now, -1);
      if (lateMembers.has(member.id) && isRecent) continue;
      if (month === now && member.shares > 1) continue;
      payments.push({
        id: newId(),
        memberId: member.id,
        type: "contribution",
        month,
        amount: member.shares * fund.contribution,
      });
    }
  }

  const loans = [
    createLoan(fund, members[1].id, addMonths(startMonth, 2)),
    createLoan(fund, members[4].id, addMonths(startMonth, 4)),
  ];
  for (const loan of loans) {
    for (let i = 0; i < loan.installments; i++) {
      const month = addMonths(loan.firstInstallmentMonth, i);
      if (month >= now) break;
      payments.push({
        id: newId(),
        memberId: loan.memberId,
        type: "installment",
        loanId: loan.id,
        month,
        amount: installmentAmount(loan, i),
      });
    }
  }

  // "demo" keeps these made-up phone numbers out of the member index, so a
  // real person with one of them never sees this fund.
  return { version: 1, demo: true, fund, members, payments, loans };
}
