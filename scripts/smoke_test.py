#!/usr/bin/env python3
"""End-to-end smoke test of a running BountyHub instance (standard library only).

Prints one PASS/FAIL line per check and exits 0 only if every check passed.

    python3 scripts/smoke_test.py                              # UI at http://localhost:3000
    python3 scripts/smoke_test.py --frontend-url http://localhost:3000
    python3 scripts/smoke_test.py --backend-url http://127.0.0.1:8000
    SMOKE_EMAIL=me@example.com SMOKE_PASSWORD=... python3 scripts/smoke_test.py

Credentials: --email/--password or SMOKE_EMAIL/SMOKE_PASSWORD (password >= 8 chars).
The app is single-user: "403 Registration is closed" on register is not a failure,
the script then logs in with the given credentials.

Safety: every hostname is under the reserved .invalid TLD, and the only scan request
sends out-of-scope targets. If it is ever accepted, the script reports FAIL and stops.
The program created by the script is deleted at the end, also after a failed check.
The registered user cannot be deleted through the API.

Verifying without Docker (backend on SQLite, 127.0.0.1:18765; run from the repo root;
set TMPDIR to a roomy directory if /tmp is full):

    python3 -m venv .venv
    .venv/bin/pip install -q -r backend/requirements.txt
    cat > .venv/smoke_server.py <<'PY'
    import uvicorn
    from app.core.database import get_engine
    from app.main import create_app
    from app.models import Base  # importing app.models registers all tables

    class FakeQueue:
        async def enqueue_recon_job(self, job_id): pass

    Base.metadata.create_all(get_engine())
    uvicorn.run(create_app(job_queue=FakeQueue()), host="127.0.0.1", port=18765)
    PY
    cd backend
    PYTHONPATH=. DATABASE_URL=sqlite:///../.venv/smoke.db JWT_SECRET=throwaway-secret \\
        ../.venv/bin/python ../.venv/smoke_server.py &
    cd ..
    python3 scripts/smoke_test.py --backend-url http://127.0.0.1:18765   # fresh DB: PASS
    python3 scripts/smoke_test.py --backend-url http://127.0.0.1:18765   # registration closed: PASS
    python3 scripts/smoke_test.py --backend-url http://127.0.0.1:1       # exits non-zero
    kill %1; rm -f .venv/smoke.db .venv/smoke_server.py
"""

import argparse
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

IN_HOST = "in.bountyhub.invalid"
OUT_HOST = "out.bountyhub.invalid"
TIMEOUT = 15


class Unreachable(Exception):
    pass


class Stop(Exception):
    """A check failed in a way that makes the remaining checks meaningless."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base: str, prefix: str = ""):
        self.base = base.rstrip("/")
        self.prefix = prefix
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar), _NoRedirect()
        )
        self.bare = urllib.request.build_opener(_NoRedirect())

    def request(self, method, path, body=None, *, cookies=True, raw=False):
        """Return (status, parsed JSON or text, headers). Never raises on HTTP errors."""
        url = f"{self.base}{path if raw else self.prefix + path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        opener = self.opener if cookies else self.bare
        try:
            resp = opener.open(req, timeout=TIMEOUT)
        except urllib.error.HTTPError as e:
            resp = e
        except (urllib.error.URLError, OSError) as e:
            raise Unreachable(f"cannot reach {self.base}: {getattr(e, 'reason', e)}") from None
        text = resp.read().decode("utf-8", "replace")
        try:
            payload = json.loads(text) if text else None
        except ValueError:
            payload = text
        return resp.status, payload, resp.headers


class Report:
    def __init__(self):
        self.failed = 0

    def check(self, name, ok, detail=""):
        print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" ({detail})" if detail and not ok else ""))
        if not ok:
            self.failed += 1
        return ok


def detail_of(status, payload):
    if isinstance(payload, dict) and "detail" in payload:
        return f"HTTP {status}: {payload['detail']}"
    return f"HTTP {status}"


def run(args, report: Report) -> None:
    frontend = args.backend_url is None
    if frontend:
        client = Client(args.frontend_url, "/api/backend")
        login_path, login_raw = "/api/auth/login", True
    else:
        client = Client(args.backend_url)
        login_path, login_raw = "/auth/login", False

    if frontend:
        status, payload, headers = client.request("GET", "/login", raw=True, cookies=False)
        location = headers.get("Location", "")
        page = "login"
        if status in (301, 302, 303, 307, 308) and location.rstrip("/").endswith("/register"):
            # First run: /login sends the visitor to /register while registration is open.
            page = "register (first-run redirect from /login)"
            status, payload, _ = client.request("GET", "/register", raw=True, cookies=False)
        report.check(
            f"{page} page renders",
            status == 200 and isinstance(payload, str) and "<html" in payload.lower(),
            f"HTTP {status}, Location {location!r}",
        )
        status, _, headers = client.request("GET", "/", raw=True, cookies=False)
        location = headers.get("Location", "")
        report.check(
            "signed-out dashboard redirects to /login",
            status in (301, 302, 303, 307, 308) and "/login" in location,
            f"HTTP {status}, Location {location!r}",
        )
        status, _, headers = client.request("GET", "/register", raw=True, cookies=False)
        location = headers.get("Location", "")
        report.check(
            "/register answers 200 or redirects to /login",
            status == 200
            or (status in (301, 302, 303, 307, 308) and "/login" in location),
            f"HTTP {status}, Location {location!r}",
        )

    status, payload, _ = client.request("GET", "/auth/status", cookies=False)
    report.check(
        "GET /auth/status returns a boolean registration_open",
        status == 200
        and isinstance(payload, dict)
        and isinstance(payload.get("registration_open"), bool),
        detail_of(status, payload),
    )

    creds = {"email": args.email, "password": args.password}
    status, payload, _ = client.request("POST", "/auth/register", creds)
    if status == 403:
        registered = "registration closed, using existing user"
    elif status == 201:
        registered = "registered"
    else:
        report.check("register or login", False, detail_of(status, payload))
        raise Stop
    status, payload, headers = client.request("POST", login_path, creds, raw=login_raw)
    if not report.check(
        f"register/login ({registered})", status == 200, detail_of(status, payload)
    ):
        raise Stop

    if frontend and args.frontend_url.lower().startswith("http://"):
        # Attribute names only: the cookie value is never printed.
        cookies = headers.get_all("Set-Cookie") or []
        attrs = [
            {a.strip().split("=")[0].lower() for a in c.split(";")[1:]} for c in cookies
        ]
        report.check(
            "login sets a session cookie without Secure over http://",
            bool(cookies) and all("secure" not in a for a in attrs),
            f"{len(cookies)} cookie(s), Secure on {sum('secure' in a for a in attrs)}",
        )

    status, payload, _ = client.request("GET", "/auth/status", cookies=False)
    report.check(
        "GET /auth/status registration_open is false after register/login",
        status == 200 and isinstance(payload, dict) and payload.get("registration_open") is False,
        detail_of(status, payload),
    )

    status, payload, _ = client.request("GET", "/auth/me")
    ok = status == 200 and isinstance(payload, dict) and payload.get("email") == args.email
    if not report.check("GET /auth/me returns the user", ok, detail_of(status, payload)):
        raise Stop

    status, payload, _ = client.request("GET", "/dashboard/summary")
    report.check(
        "GET /dashboard/summary has an integer programs count",
        status == 200
        and isinstance(payload, dict)
        and isinstance(payload.get("programs"), int)
        and not isinstance(payload.get("programs"), bool),
        detail_of(status, payload),
    )
    status, payload, _ = client.request("GET", "/recon/scans")
    report.check("GET /recon/scans returns a list", status == 200 and isinstance(payload, list),
                 detail_of(status, payload))
    if frontend:
        status, payload, headers = client.request("GET", "/settings", raw=True)
        report.check(
            "/settings page answers 200 with the session cookie",
            status == 200 and isinstance(payload, str) and "<html" in payload.lower(),
            f"HTTP {status}, Location {headers.get('Location', '')!r}",
        )

    status, payload, _ = client.request(
        "POST", "/programs", {"name": "smoke-test (safe to delete)"}
    )
    program_id = payload.get("id") if isinstance(payload, dict) else None
    if not report.check("create program", status == 201 and program_id, detail_of(status, payload)):
        raise Stop
    try:
        after_program(client, report, program_id)
    finally:
        status, payload, _ = client.request("DELETE", f"/programs/{program_id}")
        report.check("delete smoke-test program", status == 204, detail_of(status, payload))


def after_program(client: Client, report: Report, program_id: int) -> None:
    status, payload, _ = client.request(
        "POST",
        f"/programs/{program_id}/scope-rules",
        {"action": "in", "type": "domain", "value": IN_HOST},
    )
    rules_ok = report.check(
        "add in-scope rule", status == 201, detail_of(status, payload)
    )

    if rules_ok:
        status, payload, _ = client.request(
            "POST", f"/programs/{program_id}/scope-check", {"host": IN_HOST}
        )
        report.check(
            "scope-check accepts in-scope host",
            status == 200 and isinstance(payload, dict) and payload.get("in_scope") is True,
            detail_of(status, payload),
        )
        status, payload, _ = client.request(
            "POST", f"/programs/{program_id}/scope-check", {"host": OUT_HOST}
        )
        report.check(
            "scope-check rejects out-of-scope host",
            status == 200 and isinstance(payload, dict) and payload.get("in_scope") is False,
            detail_of(status, payload),
        )

    status, payload, _ = client.request("GET", "/settings/ai")
    report.check("GET /settings/ai", status == 200 and isinstance(payload, dict),
                 detail_of(status, payload))

    if not rules_ok:
        report.check("out-of-scope scan rejected", False, "skipped: scope rules missing")
    else:
        status, payload, _ = client.request(
            "POST", "/recon/scans", {"program_id": program_id, "targets": [OUT_HOST]}
        )
        if status < 300:
            report.check("out-of-scope scan rejected", False,
                         f"scan was ACCEPTED (HTTP {status}); stopping")
            raise Stop
        rejected = payload.get("rejected_targets") if isinstance(payload, dict) else None
        report.check(
            "out-of-scope scan rejected (422 with rejected_targets)",
            status == 422 and rejected == [OUT_HOST],
            detail_of(status, payload),
        )

    status, payload, _ = client.request("GET", "/auth/me", cookies=False)
    report.check("request without cookie returns 401", status == 401, detail_of(status, payload))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    where = p.add_mutually_exclusive_group()
    where.add_argument("--frontend-url", default=None,
                       help="UI base URL (default http://localhost:3000); API via /api/backend")
    where.add_argument("--backend-url", default=None,
                       help="FastAPI base URL; runs the API checks only")
    p.add_argument("--email", default=os.environ.get("SMOKE_EMAIL", "smoke@example.com"))
    p.add_argument("--password", default=os.environ.get("SMOKE_PASSWORD"))
    args = p.parse_args(argv)
    if args.backend_url is None and args.frontend_url is None:
        args.frontend_url = "http://localhost:3000"
    if not args.password:
        print("error: password required (--password or SMOKE_PASSWORD, min 8 chars)",
              file=sys.stderr)
        return 2

    report = Report()
    try:
        run(args, report)
    except Unreachable as e:
        print(f"ERROR server unreachable: {e}", file=sys.stderr)
        return 2
    except Stop:
        print("stopped early", file=sys.stderr)
    if report.failed:
        print(f"{report.failed} check(s) FAILED", file=sys.stderr)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
