import { test } from "node:test";
import assert from "node:assert/strict";
import { normalizePhone } from "./phone.js";

test("normalizes the ways people type Iranian mobile numbers", () => {
  for (const input of ["09121234567", "+989121234567", "00989121234567", "9121234567", "۰۹۱۲ ۱۲۳ ۴۵۶۷", "0912-123-4567"]) {
    assert.equal(normalizePhone(input), "09121234567", input);
  }
});

test("rejects things that are not mobile numbers", () => {
  for (const input of ["", null, "02112345678", "0912123456", "091212345678", "abc"]) {
    assert.equal(normalizePhone(input), null, String(input));
  }
});
