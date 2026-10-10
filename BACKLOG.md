# BountyHub — Backlog

Each task is independently implementable (~15 tool turns incl. tests) and branches from
`main`.

```
A  backend: GET /auth/status ──────────────┐
B  frontend: fix the sign-in route handler ├──► D  rebuild, prove it, reset, push
C  frontend: /register page + first run ───┘
```

A, B and C start now and run in parallel. They must not run `up`, `down`, `build` or any
volume command against the `bountyhub` project, must not touch the main checkout's
`infra/.env`, and must not push (spec §8 "Working in parallel on one host"). D is the only
task that touches the running stack.

## Done
1–2, 5–8. Skeleton, auth, JS crawler + secret scanner, AI triage, frontend.
3–4. Superseded by 9–10 and 12–13 (original branches never merged).
9–16. Bounty domain, strict ScopeValidator, auth on every route, recon pipeline,
migration, worker image, README, verification.
17–22. Published to GitHub as `main`, stack running in Docker, `scripts/stack.sh`,
`scripts/smoke_test.py`, README run guide.

## Open

Background (spec §3): the database is already empty, but the user cannot get in. There is
no register page, the sign-in route handler expects a token the backend never sends, and
the session cookie would be `Secure` on plain HTTP.

### A. Backend: public `GET /auth/status`
Add `AuthService.registration_open() -> bool` (true only while the users table is empty;
`register` should use it instead of its own count check) and a public route
`GET /auth/status` returning `{"registration_open": bool}` through a Pydantic schema in
`app/schemas/auth.py`. It returns nothing else: no email, no user count. Do not change
`/auth/login`, and do not put the JWT in any response body.

Tests (`backend/tests/test_auth.py`, `test_route_protection.py`): `true` on an empty
database, `false` after a registration, reachable without a cookie, and the
route-protection test's list of public routes gains `/auth/status` and nothing else.
`pytest` and `ruff check .` green.

### B. Frontend: make UI sign-in work
`frontend/src/app/api/auth/login/route.ts` reads `access_token` from the backend's JSON
body, but `POST /auth/login` returns `{id, email}` and sends the JWT in `Set-Cookie`
(`backend/app/api/auth.py`), so every correct sign-in ends in 502. Fix the handler, not
the backend (spec §4 "Auth flow"):
- Take the token from the upstream `Set-Cookie` header for cookie `AUTH_COOKIE_NAME`
  (`headers.getSetCookie()`), then set the frontend's own cookie as now. No such cookie
  on a 2xx → 502. Keep the 401 / 422 / 502 mapping.
- The `Secure` flag comes from `AUTH_COOKIE_SECURE === "true"` (default false), not from
  `NODE_ENV` / `COOKIE_SECURE`. Add `AUTH_COOKIE_SECURE: ${AUTH_COOKIE_SECURE:-false}` to
  the `frontend` service in `infra/docker-compose.yml` (one line; do not start the stack).
- Check `frontend/src/app/api/auth/logout/route.ts` clears the same cookie and still
  works against the backend's 204.

Tests (Vitest, new `frontend/tests/login-route.test.ts`, mocked `fetch`): 200 with the
cookie set from an upstream `Set-Cookie`; cookie is httpOnly and not `Secure` by default,
`Secure` when `AUTH_COOKIE_SECURE=true`; upstream 401 → 401; upstream 200 without the
cookie → 502; backend unreachable → 502. `npm test`, `npm run lint`, `npm run build` green.

### C. Frontend: `/register` page and first-run redirect
Contract in spec §4 "Auth flow"; the backend endpoint is `GET /auth/status` →
`{"registration_open": bool}` (task A; mock it here, do not wait for it).
- `components/auth/register-form.tsx` in the style of `login-form.tsx`: email, password
  (min 8), confirm password, client-side mismatch error. Add `register()` and
  `getAuthStatus()` to `features/auth/api.ts`. Register posts to
  `/api/backend/auth/register`, then calls the existing `login()` and goes to `/`.
  403 → "An account already exists" with a link to `/login`; 422 → the validation message.
- `app/register/page.tsx` in the same card layout as `/login`, titled for first-time
  setup and saying this creates the single account for this install.
- Server-side in both pages, fetch `${API_INTERNAL_URL}/auth/status` with
  `cache: "no-store"`: `/login` redirects to `/register` while registration is open,
  `/register` redirects to `/login` when it is closed. If the call fails, render the
  page's own form; `/login` then shows a "Create account" link.
- `middleware.ts`: `/register` is public like `/login` (signed-out visitors reach it,
  signed-in visitors go to `/`). Keep `safeNextPath` behaviour unchanged.
- README step "Register the single user": describe the real flow (first visit lands on
  the create-account page; afterwards it is the sign-in page).

Tests: `register-form.test.tsx` (success calls register then login, password mismatch,
403 message), `middleware.test.ts` cases for `/register` signed out and signed in.
`npm test`, `npm run lint`, `npm run build` green. Do not edit the login route handler
(task B owns it).

### D. Rebuild, prove sign-up and sign-in end to end, reset, push  (after A, B, C)
The only task that touches the stack. Use `scripts/stack.sh`; operate on project
`bountyhub` only (an unrelated `agent-office` container shares the host).
1. On `main` with A–C merged: run both test suites, then `scripts/stack.sh up`.
2. Extend `scripts/smoke_test.py` with the checks added in spec §8: `/auth/status`
   before and after registering, `/register` reachable in frontend mode, and the
   `/api/auth/login` response sets the session cookie without `Secure` on an `http://`
   URL. Keep it standard-library only and `.invalid` hostnames only.
3. Run `python3 scripts/smoke_test.py` in frontend mode with throwaway credentials and
   paste the full PASS/FAIL output in the hand-in. Also run it once against
   `http://<lan-ip>:3000`. A failure is fixed in the app with a regression test, not by
   weakening the check. No scan against a real host.
4. The user asked for a reset: run `scripts/stack.sh reset --yes`, wait for all five
   services, then prove the result instead of assuming it: `select count(*) from users`
   is 0 (psql inside the postgres container), `GET /auth/status` says
   `registration_open: true`, and `curl -I http://localhost:3000/` ends at `/register`.
5. Commit, confirm `infra/.env` is untracked, `git push origin main` (fast-forward only),
   check `git ls-remote origin main` equals local `main`. Report the URLs from
   `scripts/stack.sh urls` and exactly what the user will see on first visit.
