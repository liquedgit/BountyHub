import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE_NAME, LOGIN_PATH, REGISTER_PATH, hasValidSession } from "@/lib/auth";

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
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
  // Guard every page except Next internals, static files and API route handlers.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
