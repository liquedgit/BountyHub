# BountyHub security tests

One row per case of spec §9.6: what is done, what is expected, where it is automated and
what the last run said. Run the automated part with `scripts/security_check.py`, the unit
suites with `pytest` and `npm test`, and the manual cases with the commands below.

The **Result** column is empty on purpose; whoever runs a case writes `pass` / `fail` /
`not run` and the date there (task #7 of the backlog does this after the deploy).

## How to run

```sh
# Your own instance or the public URL. Never sends a login.
python3 scripts/security_check.py --url http://localhost:3000
python3 scripts/security_check.py --url https://<words>.trycloudflare.com

# FastAPI directly (frontend-only checks are SKIPped).
python3 scripts/security_check.py --backend-url http://127.0.0.1:8000

# Everything, ONLY against a throwaway dev backend (see below).
SECURITY_EMAIL=check@example.com SECURITY_PASSWORD='<throwaway>' \
  python3 scripts/security_check.py --backend-url http://127.0.0.1:18765 --mode full
```

Output is one `PASS` / `FAIL` / `SKIP` line per check, led by the case id; the exit code
is 0 only when nothing failed. `SKIP` means the check does not apply to that URL (for
example header checks against `--backend-url`).

- `--mode signed-out` (default) only sends unauthenticated requests. It posts to
  `/auth/register` (with an `.invalid` email) solely after `/auth/status` said
  registration is closed; if registration is open it reports FAIL and posts nothing.
- `--mode full` signs in (or registers the first account), stores sentinel AI
  credentials, creates and deletes one program and trips the login throttle, which locks
  the client out for 15 minutes. **Never run it against your real instance**: the
  sentinel credentials overwrite the stored ones and cannot be unset through the API. It
  refuses any host other than `localhost` / `127.0.0.1` unless `--i-own-this-instance` is
  given, and the email must be one the backend's validator accepts (not `.invalid`).
- It never prints a password, cookie or token, and every hostname it submits is under
  `.invalid`.

### Throwaway dev backend for `--mode full`

```sh
cd backend
D=$(mktemp -d)
export DATABASE_URL=sqlite:///$D/t.db APP_ENV=development \
       JWT_SECRET=dev-throwaway-secret-0123456789abcdef0123
alembic upgrade head
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 18765 &
# ... run the script, then:
kill %1; rm -rf "$D"
```

No worker and no Redis are attached, so no recon tool can run. The SSRF-1 check submits a
scan of `127.0.0.1` under a rule that covers it: a backend without the network guard
accepts it (and answers 503 here because nothing can queue it), which is a FAIL.

## Cases

| id | steps | expected | automated in | result |
|----|-------|----------|--------------|--------|
| AUTH-1 | Call every route except `/health`, `/auth/status`, `/auth/register`, `/auth/login` without the cookie | 401 | pytest `backend/tests/test_route_protection.py` (all routes); `security_check.py` AUTH-1 (sample of 19 routes) | |
| AUTH-2 | Send `GET /auth/me` with a JWT that is tampered, expired, signed with another secret, `alg: none`, or garbage | 401 | pytest `backend/tests/test_auth*.py`; `security_check.py` AUTH-2 (tampered, alg none, garbage; `--mode full`) | |
| AUTH-3 | With an account existing, `POST /auth/register` with a new email | 403, no account created | pytest `backend/tests/test_auth*.py`; `security_check.py` AUTH-3 | |
| AUTH-4 | 6 failed logins from one client in 15 min; then the correct password; then another client; then 50 failures across clients | 6th: 429 + `Retry-After`; 429; unaffected; 429 | pytest `backend/tests/test_auth*.py` (fake clock); `security_check.py` AUTH-4 covers the first step only (`--mode full`) | |
| AUTH-5 | `POST /auth/login` with correct credentials, read body and `Set-Cookie` | body `{id, email}` only; cookie `HttpOnly`, `SameSite=Lax`, `Secure` in tunnel mode | pytest `backend/tests/test_auth*.py`; Vitest `frontend/tests/login-route.test.ts`; `security_check.py` AUTH-5 (HttpOnly, SameSite; `--mode full`). `Secure`: manual, see below | |
| AUTH-6 | `POST /auth/login` with an unknown email, then a wrong password for a known one | identical 401 body | pytest `backend/tests/test_auth*.py` | |
| AUTH-7 | Start the app with `APP_ENV=production` and `JWT_SECRET=change-me` (or shorter than 32) | refuses to start, secret not printed | pytest `backend/tests/test_auth*.py` | |
| DATA-1 | Store Claude token and API key via `PUT /settings/ai`, then `GET`/`PUT /settings/ai` | only `claude_token_set` / `openai_api_key_set`, never a value | pytest `backend/tests/test_response_sweep.py`; `security_check.py` DATA-1 (`--mode full`) | |
| DATA-2 | Read `/auth/me`, `/auth/status`, the register and login bodies | no hash, no user count; `/auth/status` is `{registration_open}` only | pytest `backend/tests/test_auth*.py`; `security_check.py` DATA-2 (`--mode full`) | |
| DATA-3 | Store a sentinel password and AI credentials, seed rows, call every `GET` route signed in | no sentinel, no `$argon2`, no JWT in any body | pytest `backend/tests/test_response_sweep.py` | |
| DATA-4 | Run the secret scanner on a page containing a secret | assets hold only the redacted preview | pytest `backend/tests/test_recon_js_secret.py` | |
| DATA-5 | Trigger a 404, a 405, a 422 (with a sentinel in the input) and a forced 500 | no trace, path, SQL or echoed `input`; 422 items only `type`/`loc`/`msg`; 500 is `{"detail": "Internal server error"}` | pytest `backend/tests/test_hardening.py`; `security_check.py` DATA-5 (404, 405, 422; the 500 is unit-test only) | |
| DATA-6 | Look at the headers of any API response | `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` | pytest `backend/tests/test_hardening.py`; `security_check.py` DATA-6 | |
| EXP-1 | List host listeners and compose networks in tunnel mode | 3000 and 8000 on `127.0.0.1` only, no 5432/6379; tunnel container on `edge` only | manual: see below | |
| EXP-2 | `GET /api/backend/docs`, `/redoc`, `/openapi.json` on the local and the public URL | 404 | pytest `backend/tests/test_hardening.py`; `security_check.py` EXP-2 | |
| EXP-3 | Check the user and options of frontend, backend, worker | non-root; `no-new-privileges` | manual: see below | |
| HDR-1 | Fetch a page (`/login`) and read the headers | CSP, HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, no `X-Powered-By` | Vitest `frontend/tests/security.test.ts` (config); `security_check.py` HDR-1 (needs `--url`) | |
| HDR-2 | Send requests with a foreign `Origin` (a GET, a preflight, then an unsafe method through the frontend) | no `Access-Control-Allow-Origin`; unsafe method 403 | pytest `backend/tests/test_hardening.py` (no ACAO); Vitest `frontend/tests/security.test.ts`, `frontend/tests/middleware.test.ts` (403); `security_check.py` HDR-2 (403 part needs `--url`) | |
| SSRF-1 | Scan target `127.0.0.1`, `10.0.0.5`, `169.254.169.254`, `[::1]`, `localhost`, `backend` under an in-scope rule covering it | 422, listed in `rejected_targets`, no tool invoked | pytest `backend/tests/test_netguard.py`, `backend/tests/test_recon_service.py` (all six); `security_check.py` SSRF-1 (`127.0.0.1` only, `--mode full`) | |
| SSRF-2 | In-scope hostname resolving to a private address; a redirect to one | dropped before httpx/fetch; redirect not followed | pytest `backend/tests/test_netguard.py`, `backend/tests/test_fetcher.py` (fake resolver) | |
| INJ-1 | Save a program with URL `javascript:alert(1)` and open it | not rendered as a link | Vitest `frontend/tests/security.test.tsx`, `frontend/tests/programs.test.tsx` | |
| INJ-2 | Save a note with `<script>`, `<img onerror>` and a `javascript:` link | rendered as text; link removed | Vitest `frontend/tests/security.test.tsx`, `frontend/tests/notes.test.tsx` | |
| INJ-3 | Open `/login?next=//evil.example` and `next=https://evil.example`, sign in | lands on `/` | Vitest `frontend/tests/security.test.tsx`, `frontend/tests/login-form.test.tsx`; `security_check.py` INJ-3 (page neither redirects nor links to the offsite URL; needs `--url`) | |
| SEC-1 | Scan git history, tracked files, container logs and `.next/static` for secrets; check `infra/.env` | no secret; `infra/.env` untracked, mode 600 | manual: see below | |
| REC-1 | `scripts/stack.sh restart` in tunnel mode | tunnel back, `registration_open` still false, user count unchanged | manual: see below | |

Test file names for the hardening work are the ones planned in `BACKLOG.md`; if a file
was named differently when it merged, `grep -rl <case or topic> backend/tests
frontend/tests` finds it.

## Manual cases

Set up once (project `bountyhub`; read-only commands only):

```sh
cd <main checkout>
C="docker compose -p bountyhub -f infra/docker-compose.yml --env-file infra/.env"
```

### EXP-1 listeners and networks (tunnel mode on)

```sh
ss -ltn | grep -E ':(3000|8000|5432|6379)\b'
#   expect 127.0.0.1:3000 and 127.0.0.1:8000, nothing on 0.0.0.0/[::], no 5432/6379
$C --profile tunnel-quick --profile tunnel-named config | grep -nE 'published|host_ip|networks:'
for s in tunnel frontend backend worker postgres redis; do
  id=$($C ps -q $s 2>/dev/null) || continue; [ -n "$id" ] || continue
  echo "$s: $(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$id")"
done
#   expect the tunnel service on the edge network only; backend, worker, postgres and
#   redis on internal only
```

### EXP-3 container users and options

```sh
for s in frontend backend worker; do
  echo "$s uid=$($C exec -T $s id -u)"            # expect non-zero
  docker inspect -f '{{.HostConfig.SecurityOpt}}' "$($C ps -q $s)"   # expect no-new-privileges:true
done
```

### SEC-1 secrets

```sh
# Secret patterns in history and tracked files (review every hit by hand)
git log -p --all | grep -nEi 'sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|eyJ[A-Za-z0-9_-]{20,}\.|TUNNEL_TOKEN=[^ ]|JWT_SECRET=[^ c]' | head
git grep -nEi 'sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|eyJ[A-Za-z0-9_-]{20,}\.'
git ls-files infra/.env            # expect no output
stat -c '%a %n' infra/.env         # expect 600
# Container logs: no password, token, cookie or key
for s in frontend backend worker postgres redis; do $C logs "$s" 2>&1; done |
  grep -nEi 'password|token|cookie|authorization|sk-[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{20,}\.' | head
# Built bundle
$C exec -T frontend sh -c 'grep -rlEi "sk-[A-Za-z0-9]{20,}|JWT_SECRET|TUNNEL_TOKEN" .next/static || true'   # expect nothing
```

### REC-1 restart in tunnel mode

```sh
count() { $C exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from users"'; }
before=$(count)
scripts/stack.sh restart
scripts/stack.sh tunnel status            # tunnel running; `tunnel url` prints the (new) URL
curl -s http://localhost:3000/api/backend/auth/status   # {"registration_open":false}
[ "$before" = "$(count)" ] && echo "user count unchanged"
```

### AUTH-5 `Secure` flag in tunnel mode

Open the public URL in a browser, sign in, and check in the developer tools (Application
> Cookies) that the session cookie shows `HttpOnly`, `Secure` and `SameSite=Lax`.
`security_check.py` cannot sign in on the public URL by design.

## Known limits

Documented, not fixed:

- **Quick tunnel has no Cloudflare Access.** A `trycloudflare.com` URL is reachable by
  anyone who learns it; Access cannot be put in front of it. Protection is the login, the
  closed registration and the throttle. Use a named tunnel with Cloudflare Access (email
  one-time PIN) for anything beyond a short demo.
- **A JWT stays valid until it expires (24 h) after sign-out.** Sign-out clears the
  cookie; there is no server-side session list to revoke from.
- **`'unsafe-inline'` in the CSP** (`script-src` and `style-src`). Next's App Router and
  the theme script need it without a per-request nonce; a nonce-based policy is future
  work, so the CSP limits where things load from but does not stop an injected inline
  script by itself.
- **`pd-httpx` resolves DNS again itself.** The network guard resolves a hostname before
  the probe and drops it if any address is private, but a DNS record that changes between
  that check and the probe (DNS rebinding) is not covered.
- The login throttle is in-process: it resets when the backend restarts and is not shared
  between several backend processes.
