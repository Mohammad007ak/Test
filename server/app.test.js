import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { testDatabase } from "./test-db.js";
import { createApp } from "./app.js";
import { currentMonthKey } from "../src/lib/jalali.js";

const MANAGER = "09120000001";
const MEMBER = "09120000002";
const STRANGER = "09120000003";

let server;
let baseUrl;
let clock = Date.now();

before(async () => {
  const app = createApp({
    db: await testDatabase(),
    now: () => clock,
    random: () => 0,
  });
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
  const verified = await call("POST", "/api/auth/verify", {
    phone,
    code: body.devCode,
  });
  assert.equal(verified.status, 200);
  return call;
}

function sampleData() {
  const month = currentMonthKey();
  return {
    version: 1,
    fund: {
      name: "صندوق تست",
      contribution: 1000,
      loanAmount: 2000,
      installments: 2,
      startMonth: month,
      cycle: 1,
    },
    members: [
      { id: "m1", name: "مدیر", phone: MANAGER, shares: 1, joinMonth: month },
      {
        id: "m2",
        name: "عضو",
        phone: "+98 912 000 0002",
        shares: 1,
        joinMonth: month,
      },
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

  const requested = await call("POST", "/api/auth/request-code", {
    phone: "۰۹۱۲۰۰۰۰۰۰۹",
  });
  assert.equal(requested.status, 200);
  assert.match(requested.body.devCode, /^\d{5}$/);

  const wrong = await call("POST", "/api/auth/verify", {
    phone: "09120000009",
    code: "abcde",
  });
  assert.equal(wrong.status, 400);

  const ok = await call("POST", "/api/auth/verify", {
    phone: "09120000009",
    code: requested.body.devCode,
  });
  assert.equal(ok.status, 200);
  assert.deepEqual((await call("GET", "/api/me")).body, {
    phone: "09120000009",
  });

  // The code is single-use.
  const reused = await call("POST", "/api/auth/verify", {
    phone: "09120000009",
    code: requested.body.devCode,
  });
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
  const { body } = await call("POST", "/api/auth/request-code", {
    phone: "09120000011",
  });
  for (let i = 0; i < 5; i++)
    await call("POST", "/api/auth/verify", {
      phone: "09120000011",
      code: "00000",
    });
  const locked = await call("POST", "/api/auth/verify", {
    phone: "09120000011",
    code: body.devCode,
  });
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
  assert.equal(
    (
      await member("PUT", `/api/funds/${id}`, {
        data: sampleData(),
        version: 1,
      })
    ).status,
    404,
  );
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

  const first = await manager("PUT", `/api/funds/${id}`, {
    data: sampleData(),
    version: 1,
  });
  assert.deepEqual(first.body, { version: 2 });

  const stale = await manager("PUT", `/api/funds/${id}`, {
    data: sampleData(),
    version: 1,
  });
  assert.equal(stale.status, 409);
  assert.equal(stale.body.version, 2);

  const invalid = await manager("PUT", `/api/funds/${id}`, {
    data: { members: [] },
    version: 2,
  });
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
  clock += 1000;
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
  const response = await fetch(`${baseUrl}/api/auth/logout`, {
    method: "POST",
    body: "x",
  });
  assert.equal(response.status, 415);
});

test("inside the Digipay mini-app, a launch token signs the user in without SMS", async () => {
  const call = client();
  assert.equal((await call("POST", "/api/auth/digipay", { token: "bogus" })).status, 401);
  const ok = await call("POST", "/api/auth/digipay", {
    token: "sim-09120000055",
  });
  assert.equal(ok.status, 200);
  assert.deepEqual((await call("GET", "/api/me")).body, {
    phone: "09120000055",
  });
});

test("production refuses the simulator unless it's an explicit demo", async () => {
  const db = await testDatabase();
  assert.throws(() => createApp({ db, production: true }), /DEMO_MODE/);
  assert.doesNotThrow(() => createApp({ db, production: true, demo: true }));
  const sandbox = Object.assign(async () => {}, { sandbox: true });
  const live = { name: "live" };
  assert.throws(() => createApp({ db, production: true, digipay: live, sendCode: sandbox }), /sandbox/);
});

test("with an SMS sandbox key the code is sent and also shown on screen", async () => {
  const db = await testDatabase();
  const sent = [];
  const sendCode = Object.assign(async (phone, code) => sent.push(code), { sandbox: true });
  const app = createApp({ db, sendCode, demo: true });
  const server = app.listen(0);
  const res = await fetch(`http://127.0.0.1:${server.address().port}/api/auth/request-code`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ phone: "09121234567" }),
  });
  server.close();
  const body = await res.json();
  assert.equal(body.devCode, sent[0]);
});

test("joining a guaranteed plan needs explicit acceptance and the first share, then shows up in my circles", async () => {
  const call = client();
  await call("POST", "/api/auth/digipay", { token: "sim-09120000066" });
  const plans = await call("GET", "/api/plans");
  assert.equal(plans.body.plans.length, 4);

  const refused = await call("POST", "/api/circles/join", { planId: "p12-5" });
  assert.equal(refused.status, 400);

  const started = await call("POST", "/api/circles/join", {
    planId: "p12-5",
    accept: true,
  });
  assert.equal(started.status, 201);
  const checkout = await call("GET", `/api/checkouts/${started.body.checkoutId}`);
  assert.equal(checkout.body.kind, "entry");
  assert.equal(checkout.body.amount, 5_000_000);
  assert.equal((await call("GET", "/api/circles")).body.circles.length, 0);

  const paid = await call("POST", `/api/checkouts/${started.body.checkoutId}/complete`, { action: "pay" });
  assert.equal(paid.body.ok, true);
  const mine = await call("GET", "/api/circles");
  assert.equal(mine.body.circles[0].id, paid.body.circleId);
  assert.equal(mine.body.circles[0].status, "forming");

  const view = await call("GET", `/api/circles/${paid.body.circleId}`);
  assert.equal(view.body.members.find((m) => m.isMe).position, 2);
});

test("the admin panel needs the admin username and password; members keep the demo simulator buttons", async () => {
  const db = await testDatabase();
  const app = createApp({ db, demo: true, adminUsername: "boss", adminPassword: "a-long-secret" });
  const server = app.listen(0);
  const base = `http://127.0.0.1:${server.address().port}`;
  const session = () => {
    let cookie = "";
    return async (method, path, body) => {
      const r = await fetch(base + path, {
        method,
        headers: { "content-type": "application/json", cookie },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const set = r.headers.get("set-cookie");
      if (set) cookie = set.split(";")[0];
      return { status: r.status, body: await r.json() };
    };
  };
  try {
    const member = session();
    await member("POST", "/api/auth/digipay", { token: "sim-09120000019" });
    assert.equal((await member("GET", "/api/ops/overview")).status, 401);
    assert.equal((await member("GET", "/api/admin/me")).body.allowed, false);

    // A member in the demo can still fill their waiting group.
    const { checkoutId } = (await member("POST", "/api/circles/join", { planId: "p12-5", accept: true })).body;
    const { circleId } = (await member("POST", `/api/checkouts/${checkoutId}/complete`, { action: "pay" })).body;
    assert.equal((await member("POST", `/api/ops/circles/${circleId}/fill`)).status, 200);

    const boss = session();
    assert.equal((await boss("POST", "/api/admin/login", { username: "boss", password: "wrong" })).status, 401);
    assert.equal((await boss("POST", "/api/admin/login", { username: "boss", password: "a-long-secret" })).status, 200);
    assert.deepEqual((await boss("GET", "/api/admin/me")).body, { configured: true, username: "boss", allowed: true });
    assert.equal((await boss("GET", "/api/ops/overview")).body.circles.active, 1);
    await boss("POST", "/api/admin/logout");
    assert.equal((await boss("GET", "/api/ops/overview")).status, 401);

    // Five wrong passwords lock the address out, even for the right one.
    const guesser = session();
    for (let i = 0; i < 5; i++) await guesser("POST", "/api/admin/login", { username: "boss", password: `x${i}` });
    assert.equal(
      (await guesser("POST", "/api/admin/login", { username: "boss", password: "a-long-secret" })).status,
      429,
    );
  } finally {
    server.close();
  }
});

test("production refuses a short admin password", async () => {
  const db = await testDatabase();
  assert.throws(
    () => createApp({ db, production: true, demo: true, adminUsername: "boss", adminPassword: "short" }),
    /ADMIN_PASSWORD/,
  );
});

test("each account sees the first-visit tour once, whatever the device", async () => {
  const call = await login("09120000019");
  assert.deepEqual((await call("GET", "/api/me/tour")).body, { seen: false });
  assert.equal((await call("POST", "/api/me/tour", {})).status, 200);
  assert.equal((await call("POST", "/api/me/tour", {})).status, 200); // twice is fine
  // Another sign-in (another phone or browser) already knows.
  const again = await login("09120000019");
  assert.deepEqual((await again("GET", "/api/me/tour")).body, { seen: true });
  assert.deepEqual((await (await login("09120000029"))("GET", "/api/me/tour")).body, { seen: false });
});
