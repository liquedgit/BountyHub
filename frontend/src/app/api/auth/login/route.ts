import { NextResponse } from "next/server";
import { AUTH_COOKIE_NAME } from "@/lib/auth";

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
const MAX_AGE_SECONDS = 60 * 60 * 24;

export async function POST(request: Request) {
  let credentials: unknown;
  try {
    credentials = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_INTERNAL_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "Backend unavailable" }, { status: 502 });
  }

  if (!upstream.ok) {
    const status = upstream.status === 401 || upstream.status === 422 ? upstream.status : 502;
    return NextResponse.json(
      { error: status === 502 ? "Backend error" : "Invalid email or password" },
      { status },
    );
  }

  const data = (await upstream.json().catch(() => ({}))) as { access_token?: string };
  if (!data.access_token) {
    return NextResponse.json({ error: "Backend returned no token" }, { status: 502 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(AUTH_COOKIE_NAME, data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production" && process.env.COOKIE_SECURE !== "false",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
  return response;
}
