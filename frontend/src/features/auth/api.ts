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
