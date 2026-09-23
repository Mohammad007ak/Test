// Pure bookkeeping logic for a family loan fund (صندوق قرض‌الحسنه).
// The app never holds money: it only records what members paid to the
// fund manager's own bank account, and who won each monthly draw.

import { addMonths, monthsBetween } from "./jalali.js";

export function newId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

export function createEmptyState() {
  return { version: 1, fund: null, members: [], payments: [], loans: [] };
}

const isPositive = (n) => Number.isFinite(n) && n > 0;

// Shape check for data coming from a backup file or over the network.
export function isValidState(value) {
  const fund = value?.fund;
  return Boolean(
    value &&
    Array.isArray(value.members) &&
    Array.isArray(value.payments) &&
    Array.isArray(value.loans) &&
    fund &&
    typeof fund.name === "string" &&
    isPositive(fund.contribution) &&
    isPositive(fund.loanAmount) &&
    isPositive(fund.installments) &&
    /^\d{4}-\d{2}$/.test(fund.startMonth) &&
    value.members.every((m) => m && typeof m.id === "string" && isPositive(m.shares)),
  );
}

// Split a loan into equal installments; the last one absorbs the remainder.
export function installmentAmount(loan, index) {
  const base = Math.floor(loan.amount / loan.installments);
  return index === loan.installments - 1 ? loan.amount - base * (loan.installments - 1) : base;
}

export function matchesDue(payment, due) {
  return (
    payment.memberId === due.memberId &&
    payment.type === due.type &&
    payment.month === due.month &&
    (due.type !== "installment" || payment.loanId === due.loanId)
  );
}

export function paymentForDue(due) {
  return {
    id: newId(),
    memberId: due.memberId,
    type: due.type,
    loanId: due.loanId,
    month: due.month,
    amount: due.amount,
    paidAt: new Date().toISOString(),
  };
}

// Every amount a member owed up to (and including) the given month.
export function listDues(state, uptoMonth) {
  const { fund, members, loans, payments } = state;
  if (!fund) return [];
  const dues = [];

  for (const member of members) {
    const from = member.joinMonth > fund.startMonth ? member.joinMonth : fund.startMonth;
    for (const month of monthsBetween(from, uptoMonth)) {
      dues.push({
        memberId: member.id,
        type: "contribution",
        month,
        amount: member.shares * fund.contribution,
      });
    }
  }

  for (const loan of loans) {
    for (let i = 0; i < loan.installments; i++) {
      const month = addMonths(loan.firstInstallmentMonth, i);
      if (month > uptoMonth) break;
      dues.push({
        memberId: loan.memberId,
        type: "installment",
        loanId: loan.id,
        month,
        amount: installmentAmount(loan, i),
      });
    }
  }

  return dues.map((due) => ({ ...due, paid: payments.some((p) => matchesDue(p, due)) }));
}

export function duesForMonth(state, month) {
  return listDues(state, month).filter((due) => due.month === month);
}

export function overdueDues(state, currentMonth) {
  return listDues(state, currentMonth).filter((due) => !due.paid && due.month < currentMonth);
}

export function sum(items, pick = (x) => x.amount) {
  return items.reduce((total, item) => total + pick(item), 0);
}

export function fundBalance(state) {
  return sum(state.payments) - sum(state.loans);
}

export function loanProgress(state, loan) {
  const paid = state.payments.filter((p) => p.type === "installment" && p.loanId === loan.id);
  const paidAmount = sum(paid);
  return {
    paidCount: paid.length,
    paidAmount,
    remaining: loan.amount - paidAmount,
    done: paid.length >= loan.installments,
  };
}

// Each share is one ticket in the current cycle; a ticket is used up once
// it wins a loan. When no tickets remain, the fund can start a new cycle.
export function lotteryEntries(state) {
  const { fund, members, loans } = state;
  if (!fund) return [];
  return members
    .map((member) => {
      const won = loans.filter((l) => l.memberId === member.id && l.cycle === fund.cycle).length;
      return { member, tickets: member.shares - won };
    })
    .filter((entry) => entry.tickets > 0);
}

export function pickWinner(entries, random = Math.random) {
  const total = sum(entries, (e) => e.tickets);
  if (total === 0) return null;
  let ticket = Math.floor(random() * total);
  for (const entry of entries) {
    if (ticket < entry.tickets) return entry.member;
    ticket -= entry.tickets;
  }
  return entries[entries.length - 1].member;
}

export function createLoan(fund, memberId, drawMonth) {
  return {
    id: newId(),
    memberId,
    amount: fund.loanAmount,
    installments: fund.installments,
    cycle: fund.cycle,
    drawMonth,
    firstInstallmentMonth: addMonths(drawMonth, 1),
    createdAt: new Date().toISOString(),
  };
}

export function memberSummary(state, memberId, currentMonth) {
  const payments = state.payments.filter((p) => p.memberId === memberId);
  const overdue = overdueDues(state, currentMonth).filter((d) => d.memberId === memberId);
  const activeLoan = state.loans.find((l) => l.memberId === memberId && !loanProgress(state, l).done);
  return {
    contributed: sum(payments.filter((p) => p.type === "contribution")),
    overdueCount: overdue.length,
    overdueAmount: sum(overdue),
    activeLoan,
  };
}
