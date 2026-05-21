// Typed wrapper over the BFF (`/api/*`). Always same-origin: the browser
// never talks to the backend directly (Part 1.2).

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function unwrap<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T;
  let code = "INTERNAL";
  let message = res.statusText;
  try {
    const body = await res.json();
    code = body.code ?? code;
    message = body.message ?? message;
  } catch {
    // non-JSON error body; keep defaults
  }
  throw new ApiError(code, message, res.status);
}

export async function apiGet<T>(path: string): Promise<T> {
  return unwrap<T>(await fetch(`/api/${path}`, { method: "GET" }));
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return unwrap<T>(
    await fetch(`/api/${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function apiDelete<T>(path: string): Promise<T> {
  return unwrap<T>(await fetch(`/api/${path}`, { method: "DELETE" }));
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return unwrap<T>(
    await fetch(`/api/${path}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export function streamChat(
  body: unknown,
  signal: AbortSignal,
): Promise<Response> {
  return fetch("/api/chat/stream", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}
