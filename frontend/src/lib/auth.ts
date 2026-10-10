export const AUTH_COOKIE_NAME = process.env.AUTH_COOKIE_NAME ?? "access_token";
export const LOGIN_PATH = "/login";
export const REGISTER_PATH = "/register";

/** Only allow same-origin relative redirect targets (prevents open redirects). */
export function safeNextPath(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) {
    return "/";
  }
  return next;
}

/**
 * Cheap, signature-less check used by the edge middleware: the cookie must be
 * present and, if it looks like a JWT with an `exp` claim, not yet expired.
 * The backend remains the source of truth and verifies the signature.
 */
export function hasValidSession(token: string | undefined, nowMs = Date.now()): boolean {
  if (!token) return false;
  const parts = token.split(".");
  if (parts.length !== 3) return true;
  try {
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4)));
    if (typeof payload.exp === "number") return payload.exp * 1000 > nowMs;
    return true;
  } catch {
    return false;
  }
}
