import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE_NAME, LOGIN_PATH, REGISTER_PATH, hasValidSession } from "@/lib/auth";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** True when an unsafe-method request comes from another origin (CSRF defence in depth). */
function isCrossOrigin(request: NextRequest): boolean {
  if (!UNSAFE_METHODS.has(request.method)) return false;
  if (request.headers.get("sec-fetch-site")?.toLowerCase() === "cross-site") return true;
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const expected = (
    request.headers.get("x-forwarded-host") ??
    request.headers.get("host") ??
    request.nextUrl.host
  )
    .split(",")[0]
    .trim();
  try {
    return new URL(origin).host.toLowerCase() !== expected.toLowerCase();
  } catch {
    return true;
  }
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (pathname === "/api" || pathname.startsWith("/api/")) {
    if (isCrossOrigin(request)) {
      return NextResponse.json({ error: "Cross-origin request refused" }, { status: 403 });
    }
    return NextResponse.next();
  }

  const authed = hasValidSession(request.cookies.get(AUTH_COOKIE_NAME)?.value);

  if (pathname === LOGIN_PATH || pathname === REGISTER_PATH) {
    return authed ? NextResponse.redirect(new URL("/", request.url)) : NextResponse.next();
  }

  if (!authed) {
    const url = new URL(LOGIN_PATH, request.url);
    if (pathname !== "/") url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Pages get the login guard; /api/* only gets the same-origin check.
  matcher: ["/api/:path*", "/((?!api|_next/static|_next/image|favicon.ico|robots.txt).*)"],
};
