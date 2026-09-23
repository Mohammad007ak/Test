import { test } from "node:test";
import assert from "node:assert/strict";
import { createSmsSender } from "./sms.js";

const fakeFetch = (reply) => {
  const calls = [];
  const request = async (url, init) => {
    calls.push({ url: String(url), init });
    return { ok: reply.ok ?? true, status: reply.httpStatus ?? 200, json: async () => reply.body };
  };
  return { calls, request };
};

test("no provider key means dev mode", () => {
  assert.equal(createSmsSender({}), null);
});

test("SMS.ir sends the code through its verify template", async () => {
  const { calls, request } = fakeFetch({ body: { status: 1, message: "موفق" } });
  const send = createSmsSender({ SMSIR_API_KEY: "k", SMSIR_TEMPLATE_ID: "123456" }, { fetch: request });
  await send("09121234567", "04821");
  assert.equal(calls[0].url, "https://api.sms.ir/v1/send/verify");
  assert.equal(calls[0].init.headers["x-api-key"], "k");
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    mobile: "09121234567",
    templateId: 123456,
    parameters: [{ name: "CODE", value: "04821" }],
  });
});

test("SMS.ir failures surface as errors", async () => {
  const { request } = fakeFetch({ body: { status: 0, message: "قالب یافت نشد" } });
  const send = createSmsSender({ SMSIR_API_KEY: "k", SMSIR_TEMPLATE_ID: "1" }, { fetch: request });
  await assert.rejects(send("09121234567", "11111"), /قالب یافت نشد/);
  // A key without an approved template yet: SMS stays off instead of the server refusing to start.
  assert.equal(createSmsSender({ SMSIR_API_KEY: "k" }), null);
});

test("the SMS.ir sandbox uses its built-in template and flags itself", async () => {
  const { calls, request } = fakeFetch({ body: { status: 1, message: "موفق", data: { messageId: 1, cost: 1 } } });
  const send = createSmsSender({ SMSIR_API_KEY: "k", SMSIR_SANDBOX: "true" }, { fetch: request });
  assert.equal(send.sandbox, true);
  await send("09121234567", "12345");
  assert.equal(JSON.parse(calls[0].init.body).templateId, 123456);
});

test("SMS.ir wins over Kavenegar when both are set", async () => {
  const { calls, request } = fakeFetch({ body: { status: 1 } });
  const send = createSmsSender(
    { SMSIR_API_KEY: "k", SMSIR_TEMPLATE_ID: "1", KAVENEGAR_API_KEY: "x" },
    { fetch: request },
  );
  await send("09121234567", "11111");
  assert.match(calls[0].url, /sms\.ir/);
});

test("the admin panel can read the SMS.ir credit, or its exact error", async () => {
  const ok = fakeFetch({ body: { status: 1, message: "موفق", data: 1250.5 } });
  const send = createSmsSender({ SMSIR_API_KEY: "k", SMSIR_TEMPLATE_ID: "7" }, { fetch: ok.request });
  assert.deepEqual(send.info, { provider: "sms.ir", sandbox: false, templateId: 7, parameter: "CODE" });
  assert.deepEqual(await send.status(), { credit: 1250.5 });
  assert.equal(ok.calls[0].url, "https://api.sms.ir/v1/credit");

  const bad = fakeFetch({ ok: false, httpStatus: 401, body: { status: 0, message: "کلید نامعتبر است" } });
  const send2 = createSmsSender({ SMSIR_API_KEY: "x", SMSIR_TEMPLATE_ID: "7" }, { fetch: bad.request });
  await assert.rejects(send2.status(), /کلید نامعتبر است/);
});
