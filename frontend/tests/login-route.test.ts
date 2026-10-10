import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AUTH_COOKIE_NAME } from "@/lib/auth";
import { POST } from "@/app/api/auth/login/route";

function loginRequest() {
  return new Request("http://localhost:3000/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "a@b.co", password: "pw" }),
  });
}

function upstreamResponse(status: number, setCookie?: string) {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (setCookie) headers.append("Set-Cookie", setCookie);
  return new Response(JSON.stringify({ id: 1, email: "a@b.co" }), { status, headers });
}

describe("POST /api/auth/login", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  const mockFetch = () => fetch as unknown as ReturnType<typeof vi.fn>;

  it("sets the cookie from the upstream Set-Cookie header", async () => {
    mockFetch().mockResolvedValue(
      upstreamResponse(200, `${AUTH_COOKIE_NAME}=jwt.token.value; HttpOnly; Path=/; SameSite=lax`),
    );
    const res = await POST(loginRequest());
    expect(res.status).toBe(200);
    const cookie = res.cookies.get(AUTH_COOKIE_NAME);
    expect(cookie?.value).toBe("jwt.token.value");
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.sameSite).toBe("lax");
    expect(cookie?.path).toBe("/");
    expect(cookie?.secure).toBeFalsy();
  });

  it("marks the cookie Secure when AUTH_COOKIE_SECURE=true", async () => {
    vi.stubEnv("AUTH_COOKIE_SECURE", "true");
    mockFetch().mockResolvedValue(upstreamResponse(200, `${AUTH_COOKIE_NAME}=abc; HttpOnly`));
    const res = await POST(loginRequest());
    expect(res.cookies.get(AUTH_COOKIE_NAME)?.secure).toBe(true);
  });

  it("maps upstream 401 to 401", async () => {
    mockFetch().mockResolvedValue(upstreamResponse(401));
    const res = await POST(loginRequest());
    expect(res.status).toBe(401);
  });

  it("returns 502 when a 2xx has no auth cookie", async () => {
    mockFetch().mockResolvedValue(upstreamResponse(200, "other=1; Path=/"));
    const res = await POST(loginRequest());
    expect(res.status).toBe(502);
  });

  it("returns 502 when the backend is unreachable", async () => {
    mockFetch().mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await POST(loginRequest());
    expect(res.status).toBe(502);
  });
});
