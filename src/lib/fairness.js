// Provably fair draws for guaranteed circles. The same code runs on the
// server (to draw) and in the member's browser (to verify), using only
// WebCrypto so the results are identical in both places.
//
// When a circle is created the server picks a random secret and hashes it
// repeatedly into a chain: anchor = H(H(...H(secret))). Only the anchor is
// published. Each lottery reveals the next link back towards the secret, so
//   sha256(reveal_k) === reveal_{k-1}   (reveal_0 is the anchor).
// A link can't be forged without breaking SHA-256, so the server can't pick
// a different random number after the fact. Members' own random nonces,
// fixed when the circle fills, are mixed in so the server couldn't have
// tuned the chain to a membership it didn't know yet.

const encoder = new TextEncoder();

export async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(text));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

export function randomHex(bytes = 32) {
  return Array.from(crypto.getRandomValues(new Uint8Array(bytes)), (b) => b.toString(16).padStart(2, "0")).join("");
}

// Returns [anchor, reveal_1, …, reveal_length]; reveal_length is the secret.
export async function buildChain(secret, length) {
  const chain = [secret];
  for (let i = 0; i < length; i++) chain.unshift(await sha256Hex(chain[0]));
  return chain;
}

export function nonceDigest(noncesInJoinOrder) {
  return sha256Hex(noncesInJoinOrder.join("|"));
}

// Entrants are sorted so the order they're listed in can't affect the result.
export async function pickWinner({ reveal, digest, month, eligible }) {
  const entrants = [...eligible].sort();
  const seed = await sha256Hex(`${reveal}|${digest}|${month}`);
  const index = Number(BigInt(`0x${seed.slice(0, 16)}`) % BigInt(entrants.length));
  return { seed, winner: entrants[index] };
}

export async function verifyDraw({ previous, reveal, digest, month, eligible, winner }) {
  const linkOk = (await sha256Hex(reveal)) === previous;
  const { seed, winner: expected } = await pickWinner({ reveal, digest, month, eligible });
  return { linkOk, seed, expected, ok: linkOk && expected === winner };
}
