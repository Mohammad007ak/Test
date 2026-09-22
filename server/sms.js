// Sends login codes through Kavenegar's "verify lookup" API. Without an
// API key the server runs in dev mode and the code is shown on screen.

export function createSmsSender({ apiKey, template } = {}) {
  if (!apiKey) return null;
  return async function sendCode(phone, code) {
    const url = new URL(`https://api.kavenegar.com/v1/${apiKey}/verify/lookup.json`);
    url.search = new URLSearchParams({ receptor: phone, token: code, template }).toString();
    const response = await fetch(url, { method: "POST" });
    if (!response.ok) throw new Error(`SMS provider responded ${response.status}`);
  };
}
