// The calendar of a guaranteed-plan circle, shared by server and browser.
//
// The circle starts the moment its last seat is paid for. That day every
// member's first share (paid on joining) makes up month 1's pot, which goes
// to Digipay as manager and guarantor. From then on, installments are
// collected at the start of each month and paid straight out:
//   due date      same day of the month, one Jalali month after the last;
//   payment days  the due date and the four days after it (five days);
//   draw          the sixth day, when that month's pot goes to its winner.
import { addJalaliMonths } from "./jalali.js";

export const PAY_DAYS = 5;
const DAY = 24 * 60 * 60 * 1000;

export const dueAt = (startedAt, month) => addJalaliMonths(startedAt, month - 1);

// Month 1 is paid out on the start day itself.
export const drawAt = (startedAt, month) => (month === 1 ? startedAt : dueAt(startedAt, month) + PAY_DAYS * DAY);

// The last moment to pay through the gateway: the end of the fifth day.
export const lastPayDay = (startedAt, month) => drawAt(startedAt, month) - DAY;

export function scheduleOf(startedAt, months) {
  return Array.from({ length: months }, (_, i) => ({
    month: i + 1,
    dueAt: dueAt(startedAt, i + 1),
    lastPayDay: i === 0 ? startedAt : lastPayDay(startedAt, i + 1),
    drawAt: drawAt(startedAt, i + 1),
  }));
}
