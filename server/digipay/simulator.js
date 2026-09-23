// Stand-in for Digipay's services until the mini-app SDK is available. Every
// method has the shape the real adapter must implement (see ./index.js).

let counter = 0;
const ref = (kind) => `sim-${kind}-${Date.now().toString(36)}-${(++counter).toString(36)}`;

export function createDigipaySimulator() {
  return {
    name: "simulator",

    identity: {
      // Inside the Digipay app the host passes a launch token; here the
      // token is simply "sim-<phone>".
      async verifyLaunchToken(token) {
        const match = /^sim-(09\d{9})$/.exec(String(token ?? ""));
        return match ? { phone: match[1] } : null;
      },
    },

    scoring: {
      // Digipay owns the real model. For demos the last digit decides:
      // 0 → rejected, 1–3 → up to 5M a month, 4–9 → up to 25M a month.
      async check(phone) {
        const last = Number(String(phone).slice(-1));
        const monthlyLimit = last === 0 ? 0 : last <= 3 ? 5_000_000 : 25_000_000;
        return { approved: monthlyLimit > 0, monthlyLimit };
      },
    },

    payments: {
      async createMandate({ phone, monthlyAmount, months }) {
        return { mandateId: ref("mandate"), phone, monthlyAmount, months };
      },
      // Mandates created with failing: true (used for demo bots) always decline.
      async charge({ mandateId, amount }) {
        if (String(mandateId).includes("-failing-")) return { ok: false, reason: "insufficient_funds" };
        return { ok: true, ref: ref("charge"), amount };
      },
      // The real gateway returns a URL to redirect to; the simulator lets
      // the app show its own mock payment page instead.
      async createCheckout({ amount }) {
        return { checkoutRef: ref("checkout"), url: null, amount };
      },
      async verifyCheckout({ checkoutRef, action }) {
        return { ok: action === "pay", ref: action === "pay" ? ref("paid") : null, checkoutRef };
      },
    },

    payouts: {
      async send({ amount }) {
        return { ref: ref("payout"), amount };
      },
    },
  };
}
