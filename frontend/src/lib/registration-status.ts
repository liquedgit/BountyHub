const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

/** Server-side lookup of whether the first account can still be created; null if the backend is unreachable. */
export async function fetchRegistrationOpen(): Promise<boolean | null> {
  try {
    const res = await fetch(`${API_INTERNAL_URL}/auth/status`, { cache: "no-store" });
    if (!res.ok) return null;
    const body = await res.json();
    return typeof body?.registration_open === "boolean" ? body.registration_open : null;
  } catch {
    return null;
  }
}
