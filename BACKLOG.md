# BountyHub — Backlog

Each task is independently implementable (~15 tool turns incl. tests) and branches from
`main`. The contract for this round is spec §9; case ids (AUTH-1 …) are in §9.6.

```
1  backend: login throttle, JWT/secret checks ─────┐
2  backend: response hygiene, docs closed, sweep ──┤
3  backend: recon network guard ───────────────────┤
4  frontend: headers, origin check, login handler ─┼─► 7  deploy on the tunnel, verify, report
5  infra: cloudflared service, stack.sh tunnel ────┤
6  scripts/security_check.py + SECURITY_TESTS.md ──┘
```

1–6 start now, in parallel. 7 waits for all of them.

Rules for tasks 1–6 (spec §8 "Working in parallel on one host"):
- Never `up`, `down`, `build` or wipe the `bountyhub` stack, never touch the main
  checkout's `infra/.env`, never push, never start a tunnel. Task 7 is the only one.
- **The running instance holds the user's account.** Never register, sign in or send
  failed logins to it. Use a throwaway dev backend (SQLite, `127.0.0.1`, spare port).
- File ownership: 1 → `app/api/auth.py`, `app/services/auth_service.py`,
  `app/services/login_throttle.py`, `tests/test_auth*.py`; 2 → `app/main.py` handlers
  and middleware, `app/core/http.py`, `app/schemas/settings.py`, `tests/test_hardening.py`,
  `tests/test_response_sweep.py`, `tests/test_route_protection.py`; 3 → `app/recon/*`,
  `app/services/recon.py`, recon tests; 4 → `frontend/**` except `Dockerfile`; 5 →
  `infra/**`, `*/Dockerfile`, `scripts/stack.sh`, `README.md`; 6 →
  `scripts/security_check.py`, `docs/SECURITY_TESTS.md`.
  `app/core/config.py` and `app/main.py` are shared: add lines, never rewrite.
- No real network calls in tests; no recon against a real host, ever.

## Done
1–16. Backend, recon pipeline, AI triage, first frontend, migrations, worker image.
17–26. Published to GitHub as `main`, stack running, operator scripts, sign-up/sign-in.
27–35. UI and behaviour pass, rebuilt and verified (not pushed).

## Open — Cloudflare Tunnel and hardening

### 1. Backend: login throttle, timing-equal login, JWT and secret checks
Spec §9.2. Cases AUTH-2, AUTH-4, AUTH-6, AUTH-7.
- `LoginThrottle` (in-process, injectable clock, one instance on `app.state` created in
  `create_app`): 5 failures per client per 15 min, global ceiling 50; 429 with
  `Retry-After`; checked before the hash is verified; success clears the client's count.
  Client key: `CF-Connecting-IP`, else last hop of `X-Forwarded-For`, else peer address.
  Settings `login_max_failures`, `login_window_seconds`, `login_global_max_failures`.
- Unknown email spends one argon2 verification against a dummy hash; same 401 body.
- Start-up check: `APP_ENV` not `development` and `JWT_SECRET` shorter than 32 chars or
  starting with `change-me` → the app refuses to start (a clear error, not the secret).

Tests: throttle (6th attempt, correct password while locked, other client, reset on
success, window expiry with a fake clock, global ceiling, header precedence), JWT
tampered / expired / other secret / `alg: none` / garbage → 401, secret check.

### 2. Backend: docs closed, safe errors, response headers, credential sweep
Spec §9.2. Cases AUTH-1, DATA-1, DATA-2, DATA-3, DATA-5, DATA-6, EXP-2.
- `docs_url`/`redoc_url`/`openapi_url` `None` unless `EXPOSE_DOCS=true`.
- Handlers: unhandled exception → `500 {"detail": "Internal server error"}`;
  `RequestValidationError` → 422 list with `type`, `loc`, `msg` only.
- Middleware adding `X-Content-Type-Options`, `Cache-Control: no-store`,
  `Referrer-Policy` to every response. No CORS middleware.
- `openai_base_url` must be an `http(s)` URL.
- `tests/test_response_sweep.py`: register with a sentinel password, store sentinel
  Claude token and API key, seed one row of everything, call every `GET` route found by
  walking `app.routes`; no body may contain a sentinel, `$argon2`, or the session JWT.
  Also assert no response schema in `app.openapi()` has a property named `password`,
  `hashed_password`, `token`, `access_token`, `api_key` or `secret` (`*_set` allowed).

Tests: the sweep, docs 404, 500 and 422 bodies (password not echoed), headers on a
normal and an error response, no `Access-Control-Allow-Origin` for a foreign `Origin`.

### 3. Backend: recon network guard
Spec §9.3. Cases SSRF-1, SSRF-2.
- `app/recon/netguard.py`: `NetworkGuard(resolver, allow_private)` with
  `check_target(value)` and `check_resolved(host)`; `Resolver` protocol, real one on
  `socket.getaddrinfo` with a timeout. Block list and name rules as in the spec.
- `ReconService`: guard after the scope partition at submission and before every stage;
  dropped targets go to `rejected_targets` with the `blocked: …` reason; 422 when
  nothing is left. `HttpFetcher`: guard the first URL and every redirect hop.
- Setting `recon_allow_private_targets` (default false).

Tests with a fake resolver and the fake runner/fetcher: each blocked literal and name is
rejected although an `in` rule covers it and no tool is invoked; a public name resolving
to `10.0.0.5` is dropped before httpx; a redirect to `127.0.0.1` is not followed; a name
with one public and one private address is dropped; the flag turns the guard off.

### 4. Frontend: security headers, same-origin check, login handler
Spec §9.4. Cases HDR-1, HDR-2, INJ-1, INJ-2, INJ-3.
- `next.config.mjs`: `poweredByHeader: false`, `headers()` as specified. `app/robots.ts`.
- `middleware.ts`: matcher also covers `/api/:path*`; for those paths only the
  same-origin check runs (no login redirect). Existing page behaviour unchanged.
- `app/api/auth/login/route.ts`: validate the body shape, forward `CF-Connecting-IP` and
  `X-Forwarded-For`, pass 429 on with `Retry-After`; the login form shows the message.
- Check `Markdown` and `safeNextPath` against INJ-2 / INJ-3 and fix what fails.

Tests (`tests/security.test.ts(x)`, plus the existing middleware and login-route tests):
header set from the config, foreign-origin POST → 403, same-origin and header-less POST
pass, 429 passed through, bad body 400, markdown and `next` cases. `npm test`,
`npm run lint`, `npm run build` green; confirm the built app still renders with the CSP
(`npm run start` on a spare port, fetch `/login`, no CSP-blocked inline script in the
HTML that the policy would refuse).

### 5. Infra: cloudflared service, networks, `stack.sh tunnel`, container hardening
Spec §9.1. Cases EXP-1, EXP-3, REC-1.
- Compose: `tunnel` and `tunnel-named` services behind profiles, pinned image tag,
  networks `edge` / `internal`, `${FRONTEND_BIND:-0.0.0.0}:3000:3000`,
  `APP_ENV=${APP_ENV:-production}`, `security_opt`, `cap_drop`. Must still work on podman
  and on real Docker, and `stack.sh up` with the tunnel off must behave as today.
- Dockerfiles: non-root user for frontend (`node`), backend and worker (subfinder needs
  a writable `$HOME`); drop the unused `NEXT_PUBLIC_API_URL` build arg and env.
- `scripts/stack.sh`: `tunnel up|down|url|status`, tunnel mode read from the env file on
  every compose call, registration gate, `urls` shows the public URL. Editing the env
  file touches the `BOUNTYHUB_TUNNEL` line only.
- `infra/.env.example`: `BOUNTYHUB_TUNNEL=off`, `TUNNEL_TOKEN=`, `PUBLIC_HOSTNAME=`.
- README "Public access": quick tunnel, named tunnel + Cloudflare Access step by step,
  what tunnel mode changes (LAN URL closed), reboot behaviour.
- Verify without the stack: `compose config` for off / quick / named against a temp env
  file (`BOUNTYHUB_ENV_FILE`), `bash -n`, shellcheck if installed, the env-line edit on a
  temp file. Images may be built to a throwaway tag (`bountyhub-check-*`) to prove the
  non-root users start; remove exactly those tags afterwards.

### 6. `scripts/security_check.py` and `docs/SECURITY_TESTS.md`
Spec §9.5, §9.6. Written from the spec, so it can be built while 1–5 are open.
- The script with both modes, the localhost-only guard on `--mode full`, check names
  carrying the case ids. Signed-out: AUTH-1 (sample of routes from spec §4), AUTH-3,
  DATA-5, DATA-6, EXP-2, HDR-1, HDR-2, INJ-3. Full adds AUTH-2, AUTH-4, AUTH-5, DATA-1,
  DATA-2, SSRF-1 (422 on a scan of `127.0.0.1` with a covering rule).
- `docs/SECURITY_TESTS.md`: every case in §9.6 with steps, expected result and where it
  is automated, the manual commands for EXP-1, EXP-3, SEC-1, REC-1, and the known limits
  (quick tunnel without Access, JWT valid until expiry, `unsafe-inline` in the CSP,
  `pd-httpx` re-resolving).
- Try it against a throwaway dev backend from `main`; checks for work not merged yet are
  expected to fail there, say which in the hand-in.

### 7. Deploy on Cloudflare Tunnel, verify, report  (after 1–6)
The only task that touches the stack. Project `bountyhub` only. **Never `reset`, never
remove the volume, never sign in on the user's instance.**
1. On `main` with 1–6 merged: `pytest`, `ruff check .`, `npm test`, `npm run lint`,
   `npm run build`. Fix what the merge broke.
2. `security_check.py --mode full --backend-url` against a throwaway dev backend
   (SQLite, `127.0.0.1`, spare port, stopped afterwards). Every check must pass; fix the
   code or the script, whichever is wrong against spec §9.
3. `scripts/stack.sh up`, all services healthy, then `scripts/stack.sh tunnel up`
   (quick tunnel unless `TUNNEL_TOKEN` is set). `/auth/status` must still say closed.
4. `security_check.py --mode signed-out` against `http://localhost:3000` and against the
   public URL. Manual cases: EXP-1 (`ss -ltn`, `compose config`, network membership),
   EXP-3 (`id -u` in each container), SEC-1 (git history and tracked files for secret
   patterns, `docker logs` of each service, `.next/static`, mode of `infra/.env`),
   REC-1 (`stack.sh restart`, tunnel back, user count unchanged by a read-only
   `select count(*) from users`).
5. Fill the result column of `docs/SECURITY_TESTS.md` (pass / fail / not run, with the
   date). Commit on `main`. **Do not push**: the user has not asked.
6. Report: the public URL, that a quick-tunnel URL changes on restart, what passed, what
   failed or was not run, the known limits, and how to move to a named tunnel + Access.
