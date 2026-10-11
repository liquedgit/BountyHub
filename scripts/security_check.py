#!/usr/bin/env python3
"""Black-box security checks of a running BountyHub instance (standard library only).

Prints one PASS/FAIL/SKIP line per check, led by the case id from spec §9.6 and
docs/SECURITY_TESTS.md, and exits 0 only when nothing failed.

    python3 scripts/security_check.py                                  # http://localhost:3000
    python3 scripts/security_check.py --url https://<words>.trycloudflare.com
    python3 scripts/security_check.py --backend-url http://127.0.0.1:8000

--url is the frontend origin (also the public URL); API calls go through /api/backend/*.
--backend-url talks to FastAPI directly; checks that belong to the frontend are SKIPped.

--mode signed-out (default) is safe on your own instance and on the public URL. It never
sends a login. It posts to /auth/register (with an .invalid email) only after
/auth/status said registration is closed.

--mode full is ONLY for a throwaway dev backend (see docs/SECURITY_TESTS.md): it signs in
(or registers the first account), stores sentinel AI credentials in the settings, creates
and deletes a program and trips the login throttle, which locks that client out for 15
minutes. It refuses any host other than localhost/127.0.0.1 unless --i-own-this-instance
is given. Credentials: --email/--password or SECURITY_EMAIL/SECURITY_PASSWORD.

Hostnames it submits are under .invalid; it never starts a scan that could be accepted
and never prints a password, cookie or token.
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 15
EVIL_ORIGIN = "https://evil.bountyhub.invalid"
ECHO = "echo-sentinel-7f3a91"
REGISTER_EMAIL = "security-check@bountyhub.invalid"
REGISTER_PASSWORD = "Sentinel-pass-7f3a91"  # sent only to a closed /auth/register
AI_SENTINELS = ("sk-sentinel-claude-7f3a91c2", "sk-sentinel-openai-7f3a91c2")
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
LEAK_PATTERNS = [
    (re.compile(r"Traceback \(most recent call last\)"), "stack trace"),
    (re.compile(r'File "[^"]+", line \d+'), "stack trace"),
    (re.compile(r"(/home/|/usr/|/app/|/srv/|/opt/|[A-Za-z]:\\)[\w./\\-]+"), "file path"),
    (re.compile(r"\.py\b"), "python file name"),
    (re.compile(r"\b(sqlalchemy|psycopg|sqlite3?|asyncpg|alembic)\b", re.IGNORECASE), "database library"),
    (re.compile(r"\b(SELECT|INSERT INTO|UPDATE|DELETE FROM)\b[^\"]{0,80}\b(FROM|VALUES|SET|WHERE)\b"), "SQL"),
]
PROTECTED = [  # sample of spec §4 routes; writes carry an empty body so nothing can be created
    ("GET", "/auth/me"),
    ("GET", "/programs"),
    ("GET", "/programs/1"),
    ("GET", "/programs/1/scope-rules"),
    ("GET", "/programs/1/targets"),
    ("GET", "/programs/1/findings"),
    ("GET", "/programs/1/notes"),
    ("GET", "/recon/scans"),
    ("GET", "/recon/scans/1"),
    ("GET", "/recon/scans/1/assets"),
    ("GET", "/dashboard/summary"),
    ("GET", "/settings/ai"),
    ("PUT", "/settings/ai"),
    ("POST", "/programs"),
    ("POST", "/programs/1/scope-check"),
    ("POST", "/recon/scans"),
    ("POST", "/triage"),
    ("PATCH", "/programs/1"),
    ("DELETE", "/programs/1"),
]


class Unreachable(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Response:
    def __init__(self, status, text, headers):
        self.status = status
        self.text = text
        self.headers = headers
        try:
            self.json = json.loads(text) if text else None
        except ValueError:
            self.json = None

    def set_cookies(self):
        return self.headers.get_all("Set-Cookie") or []


class Client:
    """Raw HTTP client; cookies are only ever sent when passed explicitly."""

    def __init__(self, base, prefix=""):
        self.base = base.rstrip("/")
        self.prefix = prefix
        self.opener = urllib.request.build_opener(_NoRedirect())
        self.seen = []  # (label, headers) of API responses, for DATA-6

    def request(self, method, path, body=None, *, headers=None, raw=False, cookie=None, track=True):
        url = f"{self.base}{path if raw else self.prefix + path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            resp = self.opener.open(req, timeout=TIMEOUT)
        except urllib.error.HTTPError as e:
            resp = e
        except (urllib.error.URLError, OSError) as e:
            raise Unreachable(f"cannot reach {self.base}: {getattr(e, 'reason', e)}") from None
        out = Response(resp.status, resp.read().decode("utf-8", "replace"), resp.headers)
        if track and not raw:
            self.seen.append((f"{method} {path} -> {out.status}", out.headers))
        return out


class Report:
    def __init__(self):
        self.failed = 0

    def _line(self, kind, case, name, detail=""):
        print(f"{kind} {case} {name}" + (f" ({detail})" if detail else ""))

    def check(self, case, name, ok, detail=""):
        """`detail` is shown on failure (and on pass when it is a note)."""
        if ok:
            self._line("PASS", case, name)
        else:
            self._line("FAIL", case, name, detail)
            self.failed += 1
        return ok

    def skip(self, case, name, why):
        self._line("SKIP", case, name, why)


def leak_in(text):
    for pattern, label in LEAK_PATTERNS:
        if pattern.search(text):
            return label
    return None


# --------------------------------------------------------------------------- signed out


def check_auth_1(c, rep):
    bad = []
    for method, path in PROTECTED:
        body = {} if method in ("POST", "PUT", "PATCH") else None
        r = c.request(method, path, body)
        if r.status != 401:
            bad.append(f"{method} {path}={r.status}")
    rep.check("AUTH-1", f"{len(PROTECTED)} protected routes answer 401 without a cookie",
              not bad, ", ".join(bad))


def check_auth_3(c, rep):
    name = "register is refused with 403 once an account exists"
    st = c.request("GET", "/auth/status")
    if st.status != 200 or not isinstance(st.json, dict) or "registration_open" not in st.json:
        rep.check("AUTH-3", name, False, f"/auth/status gave HTTP {st.status}, nothing posted")
        return
    if st.json["registration_open"] is not False:
        rep.check("AUTH-3", name, False,
                  "registration is OPEN (first account can be claimed); nothing posted")
        return
    r = c.request("POST", "/auth/register",
                  {"email": REGISTER_EMAIL, "password": REGISTER_PASSWORD})
    if r.status == 422:
        # The email validator may reject the reserved .invalid TLD before the closed-registration
        # guard runs; registration is known to be closed, so a syntactically normal one is safe.
        r = c.request("POST", "/auth/register",
                      {"email": "security-check@example.com", "password": REGISTER_PASSWORD})
    after = c.request("GET", "/auth/status")
    rep.check("AUTH-3", name, r.status == 403 and after.json == {"registration_open": False},
              f"register gave HTTP {r.status}")


def check_data_5(c, rep):
    name = "404/405/422 bodies carry no trace, path, SQL or echoed input"
    probes = [
        ("404", c.request("GET", f"/no-such-route-{ECHO}")),
        ("405", c.request("DELETE", "/health")),
        ("422", c.request("POST", "/auth/register", {"email": ECHO, "password": 1})),
    ]
    problems = []
    got422 = False
    for label, r in probes:
        if r.status != int(label) and not (label == "422" and r.status in (403, 422)):
            problems.append(f"{label} probe answered {r.status}")
        if r.status == 422:
            got422 = True
            items = (r.json or {}).get("detail") if isinstance(r.json, dict) else None
            if not isinstance(items, list):
                problems.append("422 detail is not a list")
            else:
                for item in items:
                    extra = set(item) - {"type", "loc", "msg"} if isinstance(item, dict) else {"?"}
                    if extra:
                        problems.append(f"422 item has {sorted(extra)}")
                        break
        if ECHO in r.text:
            problems.append(f"{label} echoes the request")
        leak = leak_in(r.text)
        if leak:
            problems.append(f"{label} body shows {leak}")
    rep.check("DATA-5", name, not problems, "; ".join(problems))
    if not got422:
        rep.skip("DATA-5", "422 item shape", "no 422 produced without sending a login")


def check_data_6(c, rep):
    # Collected from every API response above; a few more cheap ones so the sample is broad.
    c.request("GET", "/health")
    c.request("GET", "/programs")
    c.request("GET", f"/no-such-route-{ECHO}")
    bad = []
    for label, h in c.seen:
        if "no-store" not in (h.get("Cache-Control") or "").lower():
            bad.append(f"{label}: Cache-Control={h.get('Cache-Control')!r}")
        if (h.get("X-Content-Type-Options") or "").lower() != "nosniff":
            bad.append(f"{label}: no nosniff")
    rep.check("DATA-6", f"{len(c.seen)} API responses carry no-store and nosniff",
              not bad, "; ".join(bad[:4]) + (" ..." if len(bad) > 4 else ""))


def check_exp_2(c, rep):
    bad = []
    for path in ("/docs", "/redoc", "/openapi.json"):
        r = c.request("GET", path)
        if r.status != 404:
            bad.append(f"{path}={r.status}")
    rep.check("EXP-2", "docs, redoc and openapi.json answer 404", not bad, ", ".join(bad))


def _follow_get(base, path, hops=3):
    c = Client(base)
    r = c.request("GET", path, raw=True, track=False)
    while r.status in (301, 302, 303, 307, 308) and hops:
        loc = urllib.parse.urljoin(base + path, r.headers.get("Location", ""))
        if urllib.parse.urlsplit(loc).netloc != urllib.parse.urlsplit(base).netloc:
            break
        r = c.request("GET", urllib.parse.urlsplit(loc).path or "/", raw=True, track=False)
        hops -= 1
    return r


def check_hdr_1(c, rep, frontend):
    name = "page carries CSP, HSTS, X-Frame-Options DENY, nosniff, Referrer-Policy, no X-Powered-By"
    if not frontend:
        rep.skip("HDR-1", name, "frontend headers; use --url")
        return
    r = _follow_get(c.base, "/login")
    h = r.headers
    csp = h.get("Content-Security-Policy") or ""
    problems = []
    if r.status != 200:
        problems.append(f"/login gave HTTP {r.status}")
    for directive in ("default-src 'self'", "frame-ancestors 'none'", "object-src 'none'"):
        if directive not in csp:
            problems.append(f"CSP lacks {directive}")
    if "max-age=" not in (h.get("Strict-Transport-Security") or ""):
        problems.append("no HSTS")
    if (h.get("X-Frame-Options") or "").upper() != "DENY":
        problems.append("X-Frame-Options not DENY")
    if (h.get("X-Content-Type-Options") or "").lower() != "nosniff":
        problems.append("no nosniff")
    if not h.get("Referrer-Policy"):
        problems.append("no Referrer-Policy")
    if h.get("X-Powered-By"):
        problems.append("X-Powered-By present")
    rep.check("HDR-1", name, not problems, "; ".join(problems))


def check_hdr_2(c, rep, frontend):
    name = "foreign Origin gets no Access-Control-Allow-Origin" + (
        "; unsafe method with it is 403" if frontend else "")
    problems = []
    acao = []
    for method, path, extra in (
        ("GET", "/health", {"Origin": EVIL_ORIGIN}),
        ("OPTIONS", "/programs", {"Origin": EVIL_ORIGIN,
                                  "Access-Control-Request-Method": "POST"}),
        ("GET", "/auth/status", {"Origin": EVIL_ORIGIN}),
    ):
        r = c.request(method, path, headers=extra)
        if r.headers.get("Access-Control-Allow-Origin") is not None:
            acao.append(f"{method} {path}")
    if acao:
        problems.append("Access-Control-Allow-Origin on " + ", ".join(acao))
    if frontend:
        for label, extra in (("Origin", {"Origin": EVIL_ORIGIN}),
                             ("Sec-Fetch-Site", {"Sec-Fetch-Site": "cross-site"})):
            r = c.request("POST", "/programs", {}, headers=extra, track=False)  # answered by the frontend
            if r.status != 403:
                problems.append(f"foreign {label} POST answered {r.status}")
    rep.check("HDR-2", name, not problems, "; ".join(problems))


def check_inj_3(c, rep, frontend):
    name = "/login?next=<offsite> neither redirects nor renders the offsite URL"
    if not frontend:
        rep.skip("INJ-3", name, "frontend page; use --url")
        return
    problems = []
    for nxt in ("//evil.bountyhub.invalid", "https://evil.bountyhub.invalid"):
        r = c.request("GET", "/login?next=" + urllib.parse.quote(nxt, safe=""),
                      raw=True, track=False)
        loc = r.headers.get("Location") or ""
        if "evil.bountyhub.invalid" in loc:
            problems.append(f"redirects to {nxt}")
        if re.search(r"""(href|action|src)=["'][^"']*evil\.bountyhub\.invalid""", r.text):
            problems.append(f"page links to {nxt}")
    rep.check("INJ-3", name, not problems, "; ".join(problems))


# --------------------------------------------------------------------------- full


def cookie_pair(resp):
    """Return 'name=value' of the session cookie from a Set-Cookie header, or None."""
    for line in resp.set_cookies():
        pair = line.split(";", 1)[0].strip()
        if "=" in pair and pair.split("=", 1)[1]:
            return pair
    return None


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def check_full(c, rep, email, password):
    # sign in, or register the first account; AUTH-3 runs once an account is known to exist
    r = c.request("POST", "/auth/login", {"email": email, "password": password})
    if r.status == 401:
        st = c.request("GET", "/auth/status")
        if isinstance(st.json, dict) and st.json.get("registration_open") is True:
            reg = c.request("POST", "/auth/register", {"email": email, "password": password})
            keys = set(reg.json) if isinstance(reg.json, dict) else set()
            rep.check("DATA-2", "register body is {id, email} only",
                      reg.status == 201 and keys == {"id", "email"}, f"HTTP {reg.status}")
            r = c.request("POST", "/auth/login", {"email": email, "password": password})
    check_auth_3(c, rep)
    if r.status != 200:
        rep.check("AUTH-5", "login succeeds with the given credentials", False, f"HTTP {r.status}")
        return
    cookie = cookie_pair(r)
    keys = set(r.json) if isinstance(r.json, dict) else set()
    set_cookie = next((s for s in r.set_cookies() if s.split("=", 1)[0] == (cookie or "=").split("=", 1)[0]), "")
    attrs = [a.strip().lower() for a in set_cookie.split(";")[1:]]
    problems = []
    if keys != {"id", "email"}:
        problems.append(f"body keys {sorted(keys)}")
    if not cookie:
        problems.append("no session cookie")
    if "httponly" not in attrs:
        problems.append("cookie not HttpOnly")
    if "samesite=lax" not in attrs:
        problems.append("cookie not SameSite=Lax")
    rep.check("AUTH-5", "login body is {id, email}; cookie HttpOnly, SameSite=Lax",
              not problems, "; ".join(problems))
    if not cookie:
        return
    name, token = cookie.split("=", 1)

    me = c.request("GET", "/auth/me", cookie=cookie)
    check_data_2(c, rep, me)
    check_auth_2(c, rep, name, token, me.status == 200)
    check_data_1(c, rep, cookie)
    check_ssrf_1(c, rep, cookie)
    check_auth_4(c, rep, email)  # last: locks this client out for 15 minutes


def check_data_2(c, rep, me):
    st = c.request("GET", "/auth/status")
    problems = []
    if set(me.json or {}) != {"id", "email"}:
        problems.append(f"/auth/me keys {sorted(me.json or {})}")
    if st.json != {"registration_open": False}:
        problems.append("/auth/status is not exactly {registration_open: false}")
    for label, text in (("/auth/me", me.text), ("/auth/status", st.text)):
        if re.search(r"argon2|\$2[aby]\$|hash|password", text, re.IGNORECASE):
            problems.append(f"{label} mentions a hash or password")
    rep.check("DATA-2", "/auth/me and /auth/status carry no hash and no user count",
              not problems, "; ".join(problems))


def check_auth_2(c, rep, name, token, valid):
    if not valid:
        rep.check("AUTH-2", "valid session cookie is accepted (control)", False, "/auth/me not 200")
        return
    parts = token.split(".")
    variants = {"garbage": "garbage"}
    if len(parts) == 3:
        sig = parts[2]
        flipped = ("A" if sig[:1] != "A" else "B") + sig[1:]
        variants["tampered signature"] = ".".join(parts[:2] + [flipped])
        try:
            pad = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(pad))
            claims["sub"] = "0"
            head = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
            variants["alg none"] = f"{head}.{b64url(json.dumps(claims).encode())}."
            variants["tampered payload"] = ".".join(
                [parts[0], b64url(json.dumps(claims).encode()), parts[2]])
        except ValueError:
            pass
    bad = []
    for label, value in variants.items():
        r = c.request("GET", "/auth/me", cookie=f"{name}={value}")
        if r.status != 401:
            bad.append(f"{label}={r.status}")
    rep.check("AUTH-2", f"{len(variants)} forged or garbage cookies answer 401", not bad, ", ".join(bad))


def check_auth_4(c, rep, email):
    wrong = "not-the-password-" + ECHO
    codes, retry = [], None
    for _ in range(6):
        r = c.request("POST", "/auth/login", {"email": email, "password": wrong})
        codes.append(r.status)
        if r.status == 429:
            retry = r.headers.get("Retry-After")
            break
    ok = codes == [401] * 5 + [429] and bool(retry) and retry.isdigit()
    rep.check("AUTH-4", "5 failed logins answer 401, the 6th 429 with Retry-After", ok,
              f"statuses {codes}, Retry-After {retry!r}")


def check_data_1(c, rep, cookie):
    claude, openai = AI_SENTINELS
    body = {"provider": "openai_compatible", "claude_token": claude,
            "openai_api_key": openai, "openai_base_url": "http://ai.bountyhub.invalid/v1"}
    put = c.request("PUT", "/settings/ai", body, cookie=cookie)
    got = c.request("GET", "/settings/ai", cookie=cookie)
    problems = []
    for label, r in (("PUT", put), ("GET", got)):
        if r.status != 200:
            problems.append(f"{label} gave HTTP {r.status}")
        if any(s in r.text for s in AI_SENTINELS):
            problems.append(f"{label} body contains a stored credential")
    if not (isinstance(got.json, dict) and got.json.get("claude_token_set") is True
            and got.json.get("openai_api_key_set") is True):
        problems.append("*_set flags are not true")
    rep.check("DATA-1", "stored AI credentials never come back, only *_set flags",
              not problems, "; ".join(problems))


def check_ssrf_1(c, rep, cookie):
    name = "scan of 127.0.0.1 under a covering in-scope rule is 422 with it rejected"
    prog = c.request("POST", "/programs", {"name": "security-check.invalid"}, cookie=cookie)
    pid = prog.json.get("id") if isinstance(prog.json, dict) else None
    if prog.status not in (200, 201) or pid is None:
        rep.check("SSRF-1", name, False, f"program create gave HTTP {prog.status}")
        return
    try:
        rule = c.request("POST", f"/programs/{pid}/scope-rules",
                         {"action": "in", "type": "ip", "value": "127.0.0.1"}, cookie=cookie)
        if rule.status not in (200, 201):
            rep.check("SSRF-1", name, False, f"scope rule create gave HTTP {rule.status}")
            return
        r = c.request("POST", "/recon/scans",
                      {"program_id": pid, "targets": ["127.0.0.1"]}, cookie=cookie)
        rejected = json.dumps(_find_key(r.json, "rejected_targets"))
        ok = r.status == 422 and "127.0.0.1" in rejected
        rep.check("SSRF-1", name, ok,
                  f"scan answered HTTP {r.status}" + (" (ACCEPTED: network guard missing)"
                                                      if r.status in (200, 201, 202) else ""))
    finally:
        c.request("DELETE", f"/programs/{pid}", cookie=cookie)


def _find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_key(v, key)
            if found is not None:
                return found
    return None


# --------------------------------------------------------------------------- main


def main(argv=None):
    p = argparse.ArgumentParser(description="BountyHub security checks (spec §9.5/§9.6).")
    p.add_argument("--url", default="http://localhost:3000",
                   help="frontend origin or public URL (default %(default)s)")
    p.add_argument("--backend-url", help="FastAPI origin, e.g. http://127.0.0.1:8000")
    p.add_argument("--mode", choices=("signed-out", "full"), default="signed-out")
    p.add_argument("--email", default=os.environ.get("SECURITY_EMAIL"))
    p.add_argument("--password", default=os.environ.get("SECURITY_PASSWORD"))
    p.add_argument("--i-own-this-instance", action="store_true",
                   help="allow --mode full against a host other than localhost/127.0.0.1")
    args = p.parse_args(argv)

    frontend = args.backend_url is None
    base = args.url if frontend else args.backend_url
    host = urllib.parse.urlsplit(base).hostname or ""
    if args.mode == "full":
        if not (args.email and args.password):
            p.error("--mode full needs --email/--password or SECURITY_EMAIL/SECURITY_PASSWORD")
        if host not in LOCAL_HOSTS and not args.i_own_this_instance:
            p.error(f"--mode full refuses host {host!r}: it signs in, stores sentinel AI "
                    "credentials and trips the login throttle. Use a throwaway dev backend "
                    "on localhost, or pass --i-own-this-instance")

    c = Client(base, "/api/backend" if frontend else "")
    rep = Report()
    try:
        r = c.request("GET", "/health")
        if r.status != 200:
            print(f"FAIL SETUP /health answered HTTP {r.status} at {base}")
            return 1
        check_auth_1(c, rep)
        if args.mode == "signed-out":
            check_auth_3(c, rep)
        check_data_5(c, rep)
        check_exp_2(c, rep)
        check_hdr_1(c, rep, frontend)
        check_hdr_2(c, rep, frontend)
        check_inj_3(c, rep, frontend)
        check_data_6(c, rep)
        if args.mode == "full":
            check_full(c, rep, args.email, args.password)
    except Unreachable as e:
        print(f"FAIL SETUP {e}")
        return 1
    print(f"{'FAILED' if rep.failed else 'OK'}: {rep.failed} check(s) failed")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
