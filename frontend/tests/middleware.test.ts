import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import { middleware } from "@/middleware";

function req(path: string, token?: string) {
  return new NextRequest(`http://localhost:3000${path}`, {
    headers: token ? { cookie: `access_token=${token}` } : {},
  });
}

function jwt(exp: number) {
  const enc = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "");
  return `${enc({ alg: "HS256" })}.${enc({ exp })}.sig`;
}

describe("auth middleware", () => {
  it("redirects unauthenticated dashboard requests to /login with next", () => {
    const res = middleware(req("/programs?x=1"));
    expect(res.status).toBe(307);
    const location = new URL(res.headers.get("location")!);
    expect(location.pathname).toBe("/login");
    expect(location.searchParams.get("next")).toBe("/programs?x=1");
  });

  it("redirects the root to /login without a next param", () => {
    const res = middleware(req("/"));
    expect(new URL(res.headers.get("location")!).search).toBe("");
  });

  it("lets authenticated requests through", () => {
    const res = middleware(req("/", jwt(Math.floor(Date.now() / 1000) + 3600)));
    expect(res.headers.get("location")).toBeNull();
  });

  it("treats an expired token as unauthenticated", () => {
    const res = middleware(req("/", jwt(Math.floor(Date.now() / 1000) - 10)));
    expect(new URL(res.headers.get("location")!).pathname).toBe("/login");
  });

  it("allows the login page when logged out and bounces it when logged in", () => {
    expect(middleware(req("/login")).headers.get("location")).toBeNull();
    const res = middleware(req("/login", jwt(Math.floor(Date.now() / 1000) + 3600)));
    expect(new URL(res.headers.get("location")!).pathname).toBe("/");
  });
});
