export interface LoginCredentials {
  email: string;
  password: string;
}

/** Calls the Next.js route handler, which authenticates against the backend and sets the httpOnly cookie. */
export async function login(credentials: LoginCredentials): Promise<void> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });
  if (!res.ok) {
    let message = "Login failed";
    try {
      message = (await res.json()).error ?? message;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}

export class RegistrationClosedError extends Error {
  constructor() {
    super("An account already exists");
    this.name = "RegistrationClosedError";
  }
}

function validationMessage(body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d as { msg?: unknown })?.msg)
      .filter((m): m is string => typeof m === "string");
    if (msgs.length) return msgs.join("; ");
  }
  return "Invalid registration details";
}

/** Creates the single account via the backend proxy, then signs in with the same credentials. */
export async function register(credentials: LoginCredentials): Promise<void> {
  const res = await fetch("/api/backend/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });
  if (res.status === 403) throw new RegistrationClosedError();
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* ignore */
    }
    throw new Error(res.status === 422 ? validationMessage(body) : "Registration failed");
  }
  await login(credentials);
}

export interface AuthStatus {
  registration_open: boolean;
}

export async function getAuthStatus(): Promise<AuthStatus> {
  const res = await fetch("/api/backend/auth/status", { cache: "no-store" });
  if (!res.ok) throw new Error("Could not load auth status");
  return res.json();
}
