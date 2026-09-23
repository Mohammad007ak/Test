import { createDigipaySimulator } from "./simulator.js";

// Everything the app needs from Digipay, behind one object:
//   identity.verifyLaunchToken(token)            → { phone } | null
//   scoring.check(phone)                         → { approved, monthlyLimit }
//   payments.createMandate({ phone, monthlyAmount, months }) → { mandateId }
//   payments.revokeMandate({ mandateId })        → { ok }
//   payments.charge({ mandateId, amount, ref })  → { ok, ref }
//   payments.createCheckout({ phone, amount, ref }) → { checkoutRef, url }
//   payments.verifyCheckout({ checkoutRef, action }) → { ok, ref }
//   payments.refund({ paymentRef, amount }) → { ok, ref }
//   payouts.send({ phone, operator, amount, ref }) → { ref }
// The live adapter is written once the mini-app SDK docs arrive.
export function createDigipay(env = process.env) {
  if (env.DIGIPAY_MODE === "live") {
    throw new Error("DIGIPAY_MODE=live is not implemented yet: waiting for the Digipay mini-app SDK.");
  }
  return createDigipaySimulator();
}
