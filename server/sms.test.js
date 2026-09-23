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
  assert.throws(() => createSmsSender({ SMSIR_API_KEY: "k" }), /SMSIR_TEMPLATE_ID/);
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
