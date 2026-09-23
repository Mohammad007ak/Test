// Sends login codes by SMS. Two providers are supported; the first one with
// an API key set wins:
//   SMS.ir     "verify" API with a template that has one parameter (the code).
//              With SMSIR_SANDBOX=true (a Sandbox key) nothing is delivered,
//              so the code is also shown on screen; the sandbox's built-in
//              template is 123456 ("کد تایید شما: #CODE#").
//   Kavenegar  "verify lookup" API with a template containing %token%
// With neither, the server runs in dev mode and shows the code on screen.

export function createSmsSender(env = {}, { fetch: request = fetch } = {}) {
  if (env.SMSIR_API_KEY) return smsIr(env, request);
  if (env.KAVENEGAR_API_KEY) return kavenegar(env, request);
  return null;
}

const SMSIR_SANDBOX_TEMPLATE = 123456;

function smsIr(env, request) {
  const sandbox = env.SMSIR_SANDBOX === "true";
  const templateId = Number(env.SMSIR_TEMPLATE_ID) || (sandbox ? SMSIR_SANDBOX_TEMPLATE : 0);
  if (!templateId) throw new Error("SMSIR_TEMPLATE_ID is required with SMSIR_API_KEY.");
  const parameter = env.SMSIR_TEMPLATE_PARAM || "CODE";
  const sendCode = async (phone, code) => {
    const response = await request("https://api.sms.ir/v1/send/verify", {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json", "x-api-key": env.SMSIR_API_KEY },
      body: JSON.stringify({ mobile: phone, templateId, parameters: [{ name: parameter, value: code }] }),
    });
    const body = await response.json().catch(() => ({}));
    // SMS.ir answers status 1 on success, anything else with a message.
    if (!response.ok || body.status !== 1) {
      throw new Error(`SMS.ir: ${response.status} ${body.status ?? ""} ${body.message ?? ""}`.trim());
    }
  };
  sendCode.sandbox = sandbox;
  return sendCode;
}

function kavenegar(env, request) {
  const template = env.KAVENEGAR_TEMPLATE ?? "sandogh-login";
  return async function sendCode(phone, code) {
    const url = new URL(`https://api.kavenegar.com/v1/${env.KAVENEGAR_API_KEY}/verify/lookup.json`);
    url.search = new URLSearchParams({ receptor: phone, token: code, template }).toString();
    const response = await request(url, { method: "POST" });
    if (!response.ok) throw new Error(`Kavenegar responded ${response.status}`);
  };
}
