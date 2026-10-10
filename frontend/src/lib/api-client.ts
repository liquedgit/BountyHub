/**
 * Browser-side API client. Requests go through the Next.js `/api/backend/*`
 * rewrite (see next.config.mjs), which proxies to the FastAPI backend and keeps
 * everything same-origin so the httpOnly auth cookie is sent automatically.
 */
export const API_BASE = "/api/backend";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.assign("/login");
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = body.detail ?? body.message ?? message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, typeof message === "string" ? message : "Request failed");
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
