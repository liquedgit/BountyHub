import { NextResponse } from "next/server";
import { AUTH_COOKIE_NAME } from "@/lib/auth";

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
const MAX_AGE_SECONDS = 60 * 60 * 24;

function tokenFromSetCookie(setCookies: string[]): string | null {
  for (const header of setCookies) {
    const pair = header.split(";", 1)[0];
    const eq = pair.indexOf("=");
    if (eq > 0 && pair.slice(0, eq).trim() === AUTH_COOKIE_NAME) {
      const value = pair.slice(eq + 1).trim();
      return value || null;
    }
  }
  return null;
}

export async function POST(request: Request) {
  let credentials: unknown;
  try {
    credentials = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  const body = credentials as { email?: unknown; password?: unknown } | null;
  if (
    !body ||
    typeof body !== "object" ||
    typeof body.email !== "string" ||
    typeof body.password !== "string"
  ) {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  for (const name of ["cf-connecting-ip", "x-forwarded-for"]) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_INTERNAL_URL}/auth/login`, {
      method: "POST",
      headers,
      body: JSON.stringify({ email: body.email, password: body.password }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "Backend unavailable" }, { status: 502 });
  }

  if (upstream.status === 429) {
    const seconds = Number.parseInt(upstream.headers.get("retry-after") ?? "", 10);
    const retryAfter = Number.isFinite(seconds) && seconds > 0 ? seconds : 60;
    const minutes = Math.max(1, Math.ceil(retryAfter / 60));
    return NextResponse.json(
      {
        error: `Too many attempts. Try again in ${minutes} ${minutes === 1 ? "minute" : "minutes"}.`,
      },
      { status: 429, headers: { "Retry-After": String(retryAfter) } },
    );
  }

  if (!upstream.ok) {
    const status = upstream.status === 401 || upstream.status === 422 ? upstream.status : 502;
    return NextResponse.json(
      { error: status === 502 ? "Backend error" : "Invalid email or password" },
      { status },
    );
  }

  const token = tokenFromSetCookie(upstream.headers.getSetCookie());
  if (!token) {
    return NextResponse.json({ error: "Backend returned no token" }, { status: 502 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(AUTH_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.AUTH_COOKIE_SECURE === "true",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
  return response;
}
