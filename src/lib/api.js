export class ApiError extends Error {
  constructor(status, body) {
    super(body?.error ?? "خطایی رخ داد.");
    this.status = status;
    this.body = body;
  }
}

export async function api(method, path, body) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, { error: "اتصال به سرور برقرار نشد. اینترنت را بررسی کنید." });
  }
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) window.dispatchEvent(new Event("sandogh:logged-out"));
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}
