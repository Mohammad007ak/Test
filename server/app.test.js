import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { openDatabase } from "./db.js";
import { createApp } from "./app.js";
import { currentMonthKey } from "../src/lib/jalali.js";

const MANAGER = "09120000001";
const MEMBER = "09120000002";
const STRANGER = "09120000003";

let server;
let baseUrl;
let clock = Date.now();

before(async () => {
  const app = createApp({ db: openDatabase(":memory:"), now: () => clock, random: () => 0 });
  server = app.listen(0);
  await new Promise((resolve) => server.once("listening", resolve));
  baseUrl = `http://localhost:${server.address().port}`;
});

after(() => server.close());

function client() {
  let cookie = "";
  return async function call(method, path, body) {
    const response = await fetch(baseUrl + path, {
      method,
      headers: { "content-type": "application/json", cookie },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const setCookie = response.headers.get("set-cookie");
    if (setCookie) cookie = setCookie.split(";")[0];
    return { status: response.status, body: await response.json() };
  };
}

async function login(phone) {
  const call = client();
  const { body } = await call("POST", "/api/auth/request-code", { phone });
  const verified = await call("POST", "/api/auth/verify", { phone, code: body.devCode });
  assert.equal(verified.status, 200);
  return call;
}

function sampleData() {
  const month = currentMonthKey();
  return {
    version: 1,
    fund: { name: "صندوق تست", contribution: 1000, loanAmount: 2000, installments: 2, startMonth: month, cycle: 1 },
    members: [
      { id: "m1", name: "مدیر", phone: MANAGER, shares: 1, joinMonth: month },
      { id: "m2", name: "عضو", phone: "+98 912 000 0002", shares: 1, joinMonth: month },
    ],
    payments: [
      { id: "p1", memberId: "m1", type: "contribution", month, amount: 1000 },
      { id: "p2", memberId: "m2", type: "contribution", month, amount: 1000 },
    ],
    loans: [],
  };
}

test("login requires the code that was sent", async () => {
  const call = client();
  assert.equal((await call("GET", "/api/me")).status, 401);

  const requested = await call("POST", "/api/auth/request-code", { phone: "۰۹۱۲۰۰۰۰۰۰۹" });
  assert.equal(requested.status, 200);
  assert.match(requested.body.devCode, /^\d{5}$/);

  const wrong = await call("POST", "/api/auth/verify", { phone: "09120000009", code: "abcde" });
  assert.equal(wrong.status, 400);

  const ok = await call("POST", "/api/auth/verify", { phone: "09120000009", code: requested.body.devCode });
  assert.equal(ok.status, 200);
  assert.deepEqual((await call("GET", "/api/me")).body, { phone: "09120000009" });

  // The code is single-use.
  const reused = await call("POST", "/api/auth/verify", { phone: "09120000009", code: requested.body.devCode });
  assert.equal(reused.status, 400);
});

test("rejects invalid phones and rapid resends", async () => {
  const call = client();
  assert.equal((await call("POST", "/api/auth/request-code", { phone: "12345" })).status, 400);
  assert.equal((await call("POST", "/api/auth/request-code", { phone: "09120000010" })).status, 200);
  assert.equal((await call("POST", "/api/auth/request-code", { phone: "09120000010" })).status, 429);
  clock += 61 * 1000;
  assert.equal((await call("POST", "/api/auth/request-code", { phone: "09120000010" })).status, 200);
});

test("locks a code after too many wrong guesses", async () => {
  const call = client();
  const { body } = await call("POST", "/api/auth/request-code", { phone: "09120000011" });
  for (let i = 0; i < 5; i++) await call("POST", "/api/auth/verify", { phone: "09120000011", code: "00000" });
  const locked = await call("POST", "/api/auth/verify", { phone: "09120000011", code: body.devCode });
  assert.equal(locked.status, 429);
});

test("manager owns the fund; members get a read-only view; strangers get nothing", async () => {
  const manager = await login(MANAGER);
  const member = await login(MEMBER);
  const stranger = await login(STRANGER);

  const created = await manager("POST", "/api/funds", { data: sampleData() });
  assert.equal(created.status, 201);
  const { id } = created.body;

  assert.deepEqual((await member("GET", "/api/funds")).body.member, [{ id, name: "صندوق تست" }]);
  assert.equal((await member("GET", `/api/funds/${id}`)).status, 404);
  assert.equal((await member("PUT", `/api/funds/${id}`, { data: sampleData(), version: 1 })).status, 404);
  assert.equal((await stranger("GET", `/api/funds/${id}/view`)).status, 404);

  const view = await member("GET", `/api/funds/${id}/view`);
  assert.equal(view.status, 200);
  assert.equal(view.body.me.name, "عضو");
  assert.equal(view.body.balance, 2000);
  assert.equal(view.body.isManager, false);
});

test("saving with a stale version is rejected", async () => {
  const manager = await login(MANAGER);
  const { id } = (await manager("POST", "/api/funds", { data: sampleData() })).body;

  const first = await manager("PUT", `/api/funds/${id}`, { data: sampleData(), version: 1 });
  assert.deepEqual(first.body, { version: 2 });

  const stale = await manager("PUT", `/api/funds/${id}`, { data: sampleData(), version: 1 });
  assert.equal(stale.status, 409);
  assert.equal(stale.body.version, 2);

  const invalid = await manager("PUT", `/api/funds/${id}`, { data: { members: [] }, version: 2 });
  assert.equal(invalid.status, 400);
});

test("draws are chosen on the server and every re-roll is visible to members", async () => {
  const manager = await login(MANAGER);
  const member = await login(MEMBER);
  const { id } = (await manager("POST", "/api/funds", { data: sampleData() })).body;

  const first = await manager("POST", `/api/funds/${id}/draws`);
  assert.equal(first.status, 201);
  assert.equal(first.body.draw.winnerId, "m1"); // random() => 0 picks the first ticket

  // Drawing again silently cancels the pending draw, but it stays on record.
  const second = await manager("POST", `/api/funds/${id}/draws`);
  const confirmed = await manager("POST", `/api/funds/${id}/draws/${second.body.draw.id}/confirm`);
  assert.equal(confirmed.status, 200);
  assert.equal(confirmed.body.data.loans.length, 1);
  assert.equal(confirmed.body.data.loans[0].drawId, second.body.draw.id);

  const again = await manager("POST", `/api/funds/${id}/draws/${first.body.draw.id}/confirm`);
  assert.equal(again.status, 400);

  const view = (await member("GET", `/api/funds/${id}/view`)).body;
  assert.deepEqual(
    view.draws.map((d) => d.status),
    ["confirmed", "cancelled"],
  );
  assert.equal(view.loans[0].viaDraw, true);
  assert.equal(view.balance, 0);

  // Balance is now below one loan, so no more draws.
  assert.equal((await manager("POST", `/api/funds/${id}/draws`)).status, 400);
});

test("mutating requests must be JSON", async () => {
  const response = await fetch(`${baseUrl}/api/auth/logout`, { method: "POST", body: "x" });
  assert.equal(response.status, 415);
});
