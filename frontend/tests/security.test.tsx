import { render } from "@testing-library/react";
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import nextConfig, { securityHeaders } from "../next.config.mjs";
import robots from "@/app/robots";
import { POST } from "@/app/api/auth/login/route";
import { Markdown } from "@/components/common/Markdown";
import { safeNextPath } from "@/lib/auth";
import { middleware } from "@/middleware";

function apiReq(method: string, headers: Record<string, string> = {}, path = "/api/backend/x") {
  return new NextRequest(`http://localhost:3000${path}`, { method, headers });
}

describe("HDR security headers", () => {
  it("HDR-1: config carries the full header set", async () => {
    expect(nextConfig.poweredByHeader).toBe(false);
    const rules = await nextConfig.headers!();
    expect(rules).toHaveLength(1);
    expect(rules[0].source).toBe("/:path*");
    const map = Object.fromEntries(rules[0].headers.map((h) => [h.key, h.value]));
    expect(Object.keys(map).sort()).toEqual(
      [
        "Content-Security-Policy",
        "Permissions-Policy",
        "Referrer-Policy",
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-Robots-Tag",
      ].sort(),
    );
    expect(map["X-Frame-Options"]).toBe("DENY");
    expect(map["X-Content-Type-Options"]).toBe("nosniff");
    expect(map["Referrer-Policy"]).toBe("no-referrer");
    expect(map["Strict-Transport-Security"]).toBe("max-age=31536000");
    expect(map["X-Robots-Tag"]).toBe("noindex, nofollow");
    const csp = map["Content-Security-Policy"];
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("'unsafe-eval'"); // test env is not production
    expect(securityHeaders).toBe(rules[0].headers);
  });

  it("HDR-2: robots disallows everything", () => {
    expect(robots().rules).toEqual({ userAgent: "*", disallow: "/" });
  });

  it("keeps the backend rewrite", async () => {
    const rewrites = (await nextConfig.rewrites!()) as { source: string }[];
    expect(rewrites[0].source).toBe("/api/backend/:path*");
  });
});

describe("same-origin check", () => {
  it("refuses a foreign-origin POST", async () => {
    const res = middleware(apiReq("POST", { origin: "https://evil.example", host: "localhost:3000" }));
    expect(res.status).toBe(403);
    expect(await res.json()).toEqual({ error: "Cross-origin request refused" });
  });

  it("refuses Sec-Fetch-Site cross-site", () => {
    expect(middleware(apiReq("DELETE", { "sec-fetch-site": "cross-site" })).status).toBe(403);
  });

  it("prefers X-Forwarded-Host over Host", () => {
    const ok = apiReq("POST", {
      origin: "https://hub.example",
      host: "internal:3000",
      "x-forwarded-host": "hub.example",
    });
    expect(middleware(ok).status).toBe(200);
    const bad = apiReq("POST", {
      origin: "https://internal:3000",
      host: "internal:3000",
      "x-forwarded-host": "hub.example",
    });
    expect(middleware(bad).status).toBe(403);
  });

  it("passes same-origin and header-less requests, never redirecting", () => {
    const same = middleware(apiReq("POST", { origin: "http://localhost:3000", host: "localhost:3000" }));
    expect(same.status).toBe(200);
    const bare = middleware(apiReq("POST", {}, "/api/auth/login"));
    expect(bare.status).toBe(200);
    expect(bare.headers.get("location")).toBeNull();
  });

  it("ignores safe methods", () => {
    expect(middleware(apiReq("GET", { origin: "https://evil.example", host: "localhost:3000" })).status).toBe(200);
  });
});

describe("login route hardening", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  function post(body: unknown, headers: Record<string, string> = {}) {
    return new Request("http://localhost:3000/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: typeof body === "string" ? body : JSON.stringify(body),
    });
  }

  it.each([["null"], ['"x"'], [{ email: "a@b.co" }], [{ email: 1, password: "p" }], [{ email: "a", password: {} }]])(
    "rejects bad body %j with 400 without calling the backend",
    async (body) => {
      const res = await POST(post(body as string));
      expect(res.status).toBe(400);
      expect(fetch).not.toHaveBeenCalled();
    },
  );

  it("passes a backend 429 on with Retry-After", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("{}", { status: 429, headers: { "Retry-After": "600" } }),
    );
    const res = await POST(post({ email: "a@b.co", password: "pw" }));
    expect(res.status).toBe(429);
    expect(res.headers.get("retry-after")).toBe("600");
    expect(await res.json()).toEqual({ error: "Too many attempts. Try again in 10 minutes." });
  });

  it("forwards client IP headers and drops extra body fields", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("{}", { status: 401 }));
    await POST(
      post(
        { email: "a@b.co", password: "pw", extra: 1 },
        { "CF-Connecting-IP": "1.2.3.4", "X-Forwarded-For": "1.2.3.4, 10.0.0.1" },
      ),
    );
    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("cf-connecting-ip")).toBe("1.2.3.4");
    expect(headers.get("x-forwarded-for")).toBe("1.2.3.4, 10.0.0.1");
    expect(JSON.parse(init.body as string)).toEqual({ email: "a@b.co", password: "pw" });
  });
});

describe("INJ markdown and redirects", () => {
  it("INJ-1: raw HTML is never rendered", () => {
    const { container } = render(
      <Markdown>{'<script>alert(1)</script>\n\n<img src=x onerror="alert(1)">\n\ntext'}</Markdown>,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("[onerror]")).toBeNull();
    expect(container.textContent).toContain("<script>"); // shown as literal text
  });

  it("INJ-2: unsafe link and image URLs are neutralised", () => {
    const { container } = render(
      <Markdown>{"[a](javascript:alert(1)) [b](JaVaScRiPt:alert(1)) [c](data:text/html,x) [d](https://ok.example) [e](mailto:a@b.co)\n\n![i](javascript:alert(1))"}</Markdown>,
    );
    const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href") ?? "");
    expect(hrefs.filter((h) => /^(javascript|data):/i.test(h))).toEqual([]);
    expect(hrefs).toContain("https://ok.example");
    expect(hrefs).toContain("mailto:a@b.co");
    for (const img of container.querySelectorAll("img")) {
      expect(img.getAttribute("src") ?? "").not.toMatch(/^javascript:/i);
    }
  });

  it("INJ-3: safeNextPath only allows same-site paths", () => {
    for (const bad of ["//evil.example", "https://evil.example", "/\\evil.example", "javascript:alert(1)", ""]) {
      expect(safeNextPath(bad)).toBe("/");
    }
    expect(safeNextPath(null)).toBe("/");
    expect(safeNextPath("/programs?x=1")).toBe("/programs?x=1");
  });
});
