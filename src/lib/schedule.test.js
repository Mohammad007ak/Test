import { test } from "node:test";
import assert from "node:assert/strict";
import { addJalaliMonths, toJalali } from "./jalali.js";
import { drawAt, dueAt, scheduleOf } from "./schedule.js";

const tehran = (iso) => new Date(`${iso}+03:30`).getTime();

test("adds Jalali months on the same day, clamping to shorter months", () => {
  const start = tehran("2026-10-07T14:00:00"); // 15 Mehr 1405
  assert.deepEqual(toJalali(new Date(start)), { year: 1405, month: 7, day: 15 });
  assert.deepEqual(toJalali(new Date(addJalaliMonths(start, 1))), { year: 1405, month: 8, day: 15 });
  assert.deepEqual(toJalali(new Date(addJalaliMonths(start, 6))), { year: 1406, month: 1, day: 15 });
  assert.equal(new Date(addJalaliMonths(start, 1)).getUTCHours(), new Date(start).getUTCHours());

  const endOfShahrivar = tehran("2026-09-22T10:00:00"); // 31 Shahrivar 1405
  assert.deepEqual(toJalali(new Date(endOfShahrivar)), { year: 1405, month: 6, day: 31 });
  assert.deepEqual(toJalali(new Date(addJalaliMonths(endOfShahrivar, 1))), { year: 1405, month: 7, day: 30 });
});

test("installments fall due monthly and the draw comes on the sixth day", () => {
  const start = tehran("2026-10-07T14:00:00"); // 15 Mehr
  assert.equal(drawAt(start, 1), start);
  assert.deepEqual(toJalali(new Date(dueAt(start, 2))), { year: 1405, month: 8, day: 15 });
  assert.deepEqual(toJalali(new Date(drawAt(start, 2))), { year: 1405, month: 8, day: 20 });
  const plan = scheduleOf(start, 12);
  assert.equal(plan.length, 12);
  assert.ok(plan.every((m, i) => i === 0 || m.drawAt > plan[i - 1].drawAt));
});
