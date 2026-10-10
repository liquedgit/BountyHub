# BountyHub — Product & Architecture Spec

## 1. Product

BountyHub is a single-user, self-hosted workspace for managing bug-bounty work and
running **authorized** reconnaissance against assets the user is explicitly allowed to
test. It runs locally via Docker on the user's own machine (Parrot OS).

Two pillars:

1. **Bounty management** — organize programs, scope, targets, findings/reports, and
   markdown notes.
2. **AI-assisted reconnaissance** — orchestrate standard recon tools (Subfinder, httpx,
   a JS/SPA endpoint crawler, a secret/leak scanner) as background jobs, then use an AI
   layer to triage and prioritize the output.

### Authorization & scope guard (hard requirement)
- Recon only runs against assets the user has marked **in-scope** for a given program.
- Every scan validates each target host against the program's in-scope rules (and
  explicit out-of-scope exclusions) **before** any tool is invoked. Out-of-scope targets
  are rejected and never passed to a subprocess or fetched over HTTP.
- The scope check is enforced server-side in the job layer, not just in the UI.
- Output of one stage is untrusted input to the next: discovered subdomains, live hosts,
  script URLs and redirects are re-validated before the next tool touches them.
- This is a tool for the user's own authorized engagements; the scope guard exists to keep
  activity within the programs' stated rules.

## 2. Scope (MVP)

In:
- Email+password auth (single user), argon2 hashing, JWT in httpOnly cookies, Next.js
  middleware route protection. **Every backend route except `/health`, `/auth/status`,
  `/auth/register` and `/auth/login` requires the auth cookie.**
- First-run account creation in the UI: a `/register` page that is only usable while no
  account exists (see §4 "Auth flow").
- Programs (platform, scope in/out, reward info), Targets, Findings/Reports (status,
  severity, payout), Markdown Notes attached to programs/findings.
- Recon jobs: Subfinder → httpx → JS endpoint crawl → secret/leak scan → AI triage, run as
  background tasks with status + polled results.
- AI triage: two interchangeable providers — (a) Claude via `claude setup-token` session
  auth, (b) any OpenAI-compatible API via API key. Provider chosen in settings.
- Docker Compose brings up the whole stack with recon tools installed in the worker image.
- A consistent, responsive UI (§4 "UI system"): overview dashboard with real numbers,
  full create/edit/delete for programs, scope rules, targets, findings and notes, scan
  history with a stage-by-stage progress view and a filterable results table, and a
  Settings page for the AI provider. Every screen has loading, empty and error states.

Out (future):
- Multi-user/teams, RBAC.
- Scheduled/recurring scans.
- Live WebSocket streaming (MVP uses polling of job status/results).
- Light-theme polish beyond "readable", charts libraries, drag-and-drop boards.

## 3. Current state (2026-10-10)

Office tasks #1–#26 are merged, `main` is in sync with `origin/main`, and the `bountyhub`
stack is running. Sign-up (`/register`, first run only) and sign-in work. The user may
have registered their account by now: **the database is theirs, never reset it.**

The user asked for a full UI and behaviour pass ("refine the UI, make it better overall",
then "do all" to: consistency, cleaner sidebar and layout, informative dashboard, loading /
empty / error states, better recon results, responsive polish, existing dark theme).
What reading the frontend (about 1,400 lines) shows today:

- **No design consistency.** The auth pages use the shadcn primitives; every feature
  component uses raw `<input>`/`<button>` with hard-coded `bg-blue-600`, `text-red-500`,
  `opacity-70`. Page titles differ in weight between pages.
- **No navigation below the `md` breakpoint**: the sidebar is `hidden md:block` and
  nothing replaces it. The active link is an exact match, so `/programs/12` highlights
  nothing.
- **Overview is a placeholder card** with no data.
- **Features the backend has but the UI does not:** AI settings (`/settings/ai` has no
  page, so a provider cannot be configured from the browser), targets, editing or
  deleting a program, entering a program's URL or reward info, editing a finding's
  description, deleting a finding, re-running triage.
- **Scans are lost on reload.** The job id lives in component state and there is no
  list-scans endpoint, so there is no scan history.
- **Bugs:**
  1. When every target is out of scope the backend answers 422 with `rejected_targets`
     at the top level of the body; `ReconDashboard` reads `detail.rejected_targets`
     (the test mocks that wrong shape), so the user sees "Failed to start scan" and no
     list of rejected targets.
  2. Triage scores are 0–100 (`AITriageService`); the UI treats them as 0–1 and colours
     everything from 0.7 up red.
  3. Mutation failures are silent: no component has an error path for create/update/delete.
  4. Two `ApiError` classes (`lib/api.ts`, `lib/api-client.ts`); only one redirects on 401,
     and it is not the one the feature pages use, so an expired session shows as
     "Failed to load".
  5. The chosen program is component state: it resets on every navigation.
  6. `ProgramDetail` renders `program.url` as an `href` without checking the scheme.
  7. The assets API does not expose `ai_label` / `ai_reason`, so the UI cannot show why
     something was ranked.

Open work is in the backlog (9 tasks). Nothing above has been reproduced in a browser;
it comes from reading the code.

## 4. Architecture

Monorepo, two apps + infra:

```
/backend      FastAPI (Python 3.12), OOP service layer, SQLAlchemy 2.x, Alembic
/frontend     Next.js (App Router, TS), Tailwind, shadcn/ui, feature-based folders
/infra        docker-compose.yml, worker Dockerfile with recon tools
/scripts      operator scripts: stack.sh (drive the stack), smoke_test.py (end-to-end check)
```

### Backend (FastAPI, OOP)
Layered design, dependency-injected:
- **API layer** (`app/api/`): routers per feature (auth, bounty, recon, settings, triage).
  Thin — validate, delegate to services. Shared deps in `app/api/deps.py`.
- **Service layer** (`app/services/`): business logic as classes
  (`AuthService`, `ProgramService`, `ReconService`, `AITriageService`, …).
- **Repository layer** (`app/repositories/`): DB access classes wrapping SQLAlchemy.
- **Domain/models** (`app/models/` SQLAlchemy on `app.models.base.Base`,
  `app/schemas/` Pydantic). Sessions come from `app.core.database.get_db` only.
- **Recon** (`app/recon/`): `ScopeValidator`, the `ReconTool` interface and one adapter
  class per tool.
- **AI providers** (`app/ai/`): `AIProvider` abstract base; `ClaudeProvider` and
  `OpenAICompatibleProvider`, selected by a factory from settings.
- **Jobs** (`app/jobs/`, registered in `app/worker.py` via ARQ + Redis): the recon
  pipeline runs as a background task writing progress/results to Postgres.

### Scope guard — single source of truth
One implementation, at `app/recon/scope.py`, based on the strict validator from
`task-3`. No other module may define scope matching.

- API: `ScopeValidator(rules)`, `.check(target) -> ScopeDecision(target, in_scope,
  reason, matched_rule)`, `.is_in_scope(target) -> bool`,
  `.partition(targets) -> (allowed, rejected)`. Rules are read by attribute
  (`action` in/out, `type`, `value`) so ORM `ScopeRule` rows work directly.
- Fail-closed: an `out` rule always wins; no matching `in` rule means rejected;
  unparseable targets or rules never match.
- `domain` — exact host only (`example.com` does not cover `sub.example.com`).
- `wildcard` — `*.example.com` covers any subdomain depth, **not** the apex. To scan the
  apex, add a `domain` rule for it.
- `ip` — single IP or CIDR; matches IP-literal targets only.
- `url` — host match plus path prefix on a segment boundary; never a raw string prefix.

### Recon pipeline
- `ReconTool` (abstract): `name: str`, synchronous
  `run(targets: Iterable[str]) -> list[ReconAssetResult]`
  (`ReconAssetResult(type: AssetType, value, source, metadata)`), as already on `master`.
- Subprocess tools take an injectable `CommandRunner`; `SubprocessRunner` is the only
  place a process is spawned (argv list, never a shell, with timeout). Tests inject a
  fake runner. The ProjectDiscovery httpx binary is installed as `pd-httpx` to avoid
  clashing with the Python `httpx` package; binary paths are configurable in settings.
- HTTP-fetching tools take an injectable `Fetcher`; the real one enforces timeouts, a
  response size cap, and re-validates the final URL of any redirect against scope.
- `ReconService` owns the order: scope → subfinder → httpx → js_crawler →
  secret_scanner → triage. It re-loads scope rules when the job starts, partitions the
  targets before every stage, records rejected targets on the job, and updates
  `current_stage`. AI triage is best-effort: a provider failure is recorded but does
  not fail the scan.
- The ARQ job is a thin wrapper (`asyncio.to_thread`) around `ReconService.run_job`.

### HTTP API (contract the frontend already uses — do not rename)
- `GET/POST /programs`, `GET/PATCH/DELETE /programs/{id}`
- `GET/POST /programs/{id}/{scope-rules|targets|findings|notes}`,
  `GET/PATCH/DELETE /programs/{id}/{…}/{item_id}`
- `POST /programs/{id}/scope-check` → `{host, in_scope, reason}`
- `POST /recon/scans` `{program_id, targets[]}` → 202 job; 422 with `rejected_targets`
  when nothing is in scope. `GET /recon/scans/{id}`, `GET /recon/scans/{id}/assets`.
- `GET /recon/scans?program_id=&limit=` → jobs, newest first (`limit` default 20, max
  100; `program_id` optional). Same item shape as `GET /recon/scans/{id}`.
- `GET /dashboard/summary` → counts for the overview page:
  `{programs, targets, notes, findings: {total, open, by_status, by_severity},
  payout_cents_paid, scans: {total, active}, ai_configured, recent_findings[5],
  recent_scans[5]}`. `open` = status not in duplicate/rejected/resolved/paid;
  `by_status` and `by_severity` carry every enum value, zero included;
  `payout_cents_paid` sums `payout_cents` of `paid` findings; `active` = queued or
  running; `ai_configured` = a provider is selected and its credential is stored.
  `recent_findings` items: `{id, program_id, program_name, title, severity, status,
  updated_at}`; `recent_scans` items: `{id, program_id, program_name, status,
  current_stage, target_count, created_at, finished_at}` (`program_name` null if the
  program is gone).
- `GET/PUT /settings/ai`, `POST /triage`, `/auth/{register,login,logout,me}`, `/health`.
- `GET /auth/status` (public) → `{"registration_open": bool}`: true only while the
  `users` table is empty. It returns nothing else (no email, no count).
- `POST /auth/login` returns `{id, email}` and sets the JWT as an httpOnly cookie. The
  token is **never** in a response body; do not add an `access_token` field.
- Field names follow `frontend/src/lib/types.ts`: scope rule `action`/`type`/`value`;
  job `status`, `current_stage`, `targets`, `rejected_targets`, `error`, timestamps;
  asset `asset_type`, `value`, `source`, `meta`, `triage_score` (0–100), `triage_label`,
  `triage_reason`. The backend schema maps DB columns (`asset_metadata`, `ai_score`,
  `ai_label`, `ai_reason`) onto these names. Program, target, finding and note read
  models carry `created_at` and `updated_at`.
- Changes to this contract are additive only: no field or route is renamed or removed.

### Frontend (Next.js)
- App Router, TS, server components for data fetch, client components for interactivity.
- `components/ui` (shadcn), `components/<feature>`, `app/(dashboard)/<feature>` routes.
- Dark mode, dashboard overview, feature pages for programs/findings/recon/notes.
- Auth via httpOnly cookie; middleware guards `(dashboard)` routes. Browser calls go
  through the `/api/backend/*` rewrite so the cookie is same-origin.

#### UI system
One look across the app: dense, quiet, dark by default (Linear / Vercel style), light
theme kept working through the toggle. Violet stays the primary colour.

- **Tokens** live in `globals.css` + `tailwind.config.ts`: the shadcn set plus
  `success`, `warning`, `info`. Feature code uses tokens only: no `bg-blue-600`,
  `text-red-500` or `opacity-*` for meaning.
- **Primitives** in `components/ui/` (shadcn style, one file each): button, input,
  label, textarea, select (styled native `<select>`), card, badge, table, tabs, dialog,
  sheet, skeleton, toaster (`sonner`). Feature code never uses a raw
  `<input>`/`<button>`/`<select>`.
- **Shared pieces** in `components/common/`: `PageHeader` (title, description, actions),
  `EmptyState`, `ErrorState` (with retry), list/table skeletons, `ConfirmDialog`,
  `StatCard`, `SeverityBadge`, `StatusBadge` (finding status and job status),
  `CopyButton`, `Markdown` (react-markdown, styled, links open in a new tab with
  `rel="noopener noreferrer"`). `lib/format.ts` has date, relative-time, money and
  duration formatting.
- **Every data view has four states:** skeleton while loading, `EmptyState` with the
  next action when there is nothing, `ErrorState` with retry on a failed query, and the
  data. Every mutation shows a pending state on its button, a toast on success where the
  result is not otherwise visible, and the server's message on failure. Every delete
  goes through `ConfirmDialog`.
- **One API client** (`lib/api.ts`): one `ApiError(status, message, body)`, the message
  taken from FastAPI's `detail` (string or validation list); a 401 from any call other
  than login sends the browser to `/login?next=<path>`. `lib/types.ts` mirrors the HTTP
  contract. Only the foundation task edits these two files, `components/ui/*`,
  `components/common/*` and `package.json`; a feature task that needs a missing
  primitive adds a **new** file.
- **Program context:** pages that work on one program (findings, notes, recon) keep it
  in the URL as `?program=<id>` and remember the last one in `localStorage`; with a
  single program it is selected automatically.
- **Layout:** sidebar on `md` and up; below that a top bar whose menu button opens the
  same navigation in a sheet. Nav: Overview, Programs, Findings, Notes, Recon, and
  Settings at the bottom; a nested route highlights its parent, with
  `aria-current="page"`. Content sits in a centred `max-w-6xl` container. Usable at
  360 px wide: tables scroll inside their own container, forms stack.
- **Accessibility:** every control has a label, dialogs trap focus (Radix), focus rings
  are visible, colour is never the only signal (badges carry text).
- **Tests:** one Vitest file per feature (`tests/programs.test.tsx`, `findings`,
  `notes`, `recon`, `settings`, `dashboard`, `shell`), so parallel tasks do not edit the
  same test file.

#### Pages
- `/` Overview: stat cards, findings by severity, recent findings, recent scans, a
  getting-started checklist while there are no programs, and a callout when no AI
  provider is configured. Data from `GET /dashboard/summary`.
- `/programs`: searchable list, "New program" dialog (name, platform, URL, reward info).
  `/programs/[id]`: header with edit and delete, tabs **Scope** (in/out rules, help text
  per rule type, a "test a host" box on `scope-check`) and **Targets**, and links to the
  program's findings, notes and recon.
- `/findings`: board by status with severity badges and a totals strip; a dialog to edit
  everything on a finding or delete it. `/notes`: searchable list, editor with
  Edit/Preview, unsaved-changes state, optional link to a finding.
- `/recon`: launcher, scan history for the program, the selected scan (`?scan=<id>`)
  with a stage stepper (scope → subfinder → httpx → js_crawler → secret_scanner →
  triage), rejected targets, warnings and error, and results in tabs per asset type with
  filter, score, label and reason. Secrets are shown only as the redacted preview the
  backend stores.
- `/settings`: AI provider (Claude Code token or OpenAI-compatible). Credentials are
  write-only: the page shows "saved" or "not set", never a value, and a blank field on
  save leaves the stored secret unchanged.

#### Auth flow
- Public pages: `/login` and `/register`. The middleware lets a signed-out visitor reach
  both and sends a signed-in visitor from either to `/`.
- First run: `/login` asks the backend for `/auth/status` on the server; while
  `registration_open` is true it redirects to `/register`. `/register` redirects to
  `/login` once registration is closed. If the status call fails, each page renders its
  own form and `/login` shows a "Create account" link.
- `RegisterForm` (`components/auth/register-form.tsx`): email, password (min 8, same as
  the backend), confirm password. It posts to `/api/backend/auth/register`, then signs in
  through `/api/auth/login` and goes to `/`. A 403 shows "An account already exists" with
  a link to `/login`; a 422 shows the validation message.
- `POST /api/auth/login` (Next route handler) forwards the credentials to the backend,
  takes the JWT from the backend's `Set-Cookie` header (cookie `AUTH_COOKIE_NAME`) and
  sets it as its own httpOnly, `SameSite=Lax`, `path=/` cookie. Backend 401/422 pass
  through as "Invalid email or password"; a missing cookie is a 502.
- The cookie's `Secure` flag comes from `AUTH_COOKIE_SECURE` (default `false`), the same
  variable the backend reads, passed to the frontend service in compose. It is not
  derived from `NODE_ENV`: the app is served over plain HTTP on the LAN.

### Data model (core tables)
`users`, `programs`, `scope_rules` (action in/out, type domain/wildcard/ip/url, value),
`targets`, `findings`, `notes`, `recon_jobs` (program_id, status, current_stage,
targets, rejected_targets, error, created/started/finished), `recon_assets` (job_id FK,
asset_type, value, source, metadata, ai_score, ai_label, ai_reason), `settings`.

## 5. Tech stack
- Backend: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, ARQ, Redis, argon2-cffi,
  python-jose (JWT), pytest + httpx test client.
- Frontend: Next.js 14+, TypeScript, Tailwind, shadcn/ui, React Query, Vitest + RTL.
- Recon: subfinder, httpx (ProjectDiscovery) binaries in worker image; JS crawler and
  secret scanner implemented as adapter classes.
- Infra: Docker Compose (postgres, redis, backend, worker, frontend).

## 6. Running & tests
- **Up:** `cp infra/.env.example infra/.env` (set real values), then
  `docker compose -f infra/docker-compose.yml up -d --build`
  (backend applies Alembic migrations on start). App: `http://localhost:3000`.
- **Backend tests:** `cd backend && pip install -r requirements.txt -r requirements-dev.txt
  && pytest` (SQLite + fakes; subprocess runner, fetcher and AI providers are mocked —
  no real network/tool calls in tests).
- **Backend lint:** `cd backend && ruff check .`
- **Frontend tests:** `cd frontend && npm ci && npm test` (Vitest).
- **Frontend lint/build:** `npm run lint`, `npm run build`.
- **Stack by hand:** `scripts/stack.sh up | down | ps | logs | urls | reset --yes` (§8).
- **End-to-end check of a running stack:** `python3 scripts/smoke_test.py` (§8). It is
  not part of the unit suites and is never run in a way that reaches a real host.
- All merges must keep both suites green and must not make real external calls in tests.

## 7. Conventions
- Backend OOP service/repository layering; no business logic in routers.
- Recon adapters never bypass `ScopeValidator`; scope matching lives in one module.
- Every router except health and auth status/login/register depends on `get_current_user`.
- Secrets/tokens stored only in the `settings` table (local), never logged or returned.
- **Integration workflow:** the default branch is `main`. Branch from it; before handing in, merge it into the branch and re-run
  the tests. `backend/app/main.py`, `backend/app/models/__init__.py` and
  `backend/requirements.txt` are shared registration files — add lines, never rewrite
  them. Do not delete existing local `task-*` branches or their worktrees.

## 8. Publishing & local deployment

### GitHub
- Remote `origin` = `https://github.com/liquedgit/BountyHub.git`. It exists, is empty and
  is **public**. Auth is the host's `gh auth login` (account `liquedgit`, https protocol,
  `repo` scope); never ask for, print or store a token.
- The full existing history is published — not a fresh `git init`. Local `master` is
  renamed to `main` and pushed with upstream tracking. Only `main` is pushed; `task-*`
  branches and `worktrees/` stay local.
- Because the repo is public, nothing secret may be in any pushed commit. Tracked env
  files are `*.env.example` with placeholders only; `infra/.env` is gitignored.
- Plain fast-forward pushes only. No `--force`, no history rewriting.
- The repo is public. A push happens only in a task whose description says so; the
  UI pass (backlog tasks 1–9) does not push.

### Running on the user's laptop
- On this host `docker` is **podman 5.4 emulating the Docker CLI**, with docker-compose
  v2.26 as the external compose provider. Compose needs the podman API socket
  (`systemctl --user start podman.socket`, `DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock`),
  and podman may reject unqualified image names — use `docker.io/library/...`.
  Anything changed for podman must still work on real Docker.
- Compose project name is fixed (`name: bountyhub`) so containers, network and volume are
  the same whether started from the main checkout or a worktree.
- Secrets live in `infra/.env` of the **main checkout**
  (`/home/liqued/agent-office/workspace/bountyhub/infra/.env`, mode 600, gitignored),
  generated once (`openssl rand -hex 32`) and reused, because the Postgres volume is
  initialised with that password. From a worktree, pass it with `--env-file`.
- Published ports: frontend `3000` on all interfaces (the user may browse from another
  machine on the LAN); backend `127.0.0.1:8000` only; Postgres and Redis are not
  published (host port 5432 is already taken by another service). The browser only
  ever talks to `:3000` — API calls go through the `/api/backend/*` rewrite.
- A container named `agent-office` runs on the same host and is **not ours**. Only ever
  operate on the `bountyhub` compose project: no `docker system prune`, no
  `docker rm`/`stop` by pattern, no volume prune.
- Deployment checks never run recon against a real third-party host. Verify the tools
  with `subfinder -version` / `pd-httpx -version` inside the worker container.
- The stack is left running (`up -d`). **The database belongs to the user**: once
  `GET /auth/status` says `registration_open: false`, never run `reset`, never remove the
  volume, and never register or sign in on their instance (we do not have their
  password and must not ask for it). Authenticated end-to-end checks then run against a
  throwaway dev backend (SQLite, `127.0.0.1`, spare port) instead. Only if registration
  is still open may a throwaway user be created, and then a `reset` puts it back to empty.
- `scripts/stack.sh up` rebuilds images and keeps the volume; that is the way to deploy
  a new frontend or backend build.

### Working in parallel on one host
There is one laptop, one compose project, one running stack and one Postgres volume, so
parallelism is limited by who may touch them.
- Only one task at a time may run `up`, `down`, `build` or a volume wipe against project
  `bountyhub`. In the current backlog that is task 9 only; tasks 1–8 never touch the stack.
- A task running alongside them must not start, stop, rebuild or wipe the stack, and must
  not edit `infra/docker-compose.yml` or any Dockerfile. Read-only `ps` and `config` are
  fine.
- A parallel task must never create or overwrite the main checkout's `infra/.env`: the
  Postgres volume is initialised with that password, so a second generated file locks
  the database out. Test env-file creation against a temp path.
- A dev backend started to test a script uses SQLite, binds `127.0.0.1` on a spare port
  (not 3000, 8000 or 5432) and is stopped before hand-in.

### Operator scripts (`/scripts`)
- **`scripts/stack.sh`** — the supported way to drive the stack by hand. Subcommands:
  `up` (`up -d --build`), `down`, `restart`, `ps`, `logs [service]`, `config`, `urls`,
  `reset --yes`. It always uses `infra/docker-compose.yml`, project `bountyhub` and the
  main checkout's `infra/.env` (override with `BOUNTYHUB_ENV_FILE`), resolved from the
  script's own location so it works from any directory.
  - When `docker` is podman it starts the user's `podman.socket` and exports
    `DOCKER_HOST`; on real Docker it does neither.
  - `up` creates the env file from `infra/.env.example` with generated secrets only when
    it is missing — never overwrites, never prints a secret, mode 600.
  - `down` never removes volumes. Only `reset` does (`down -v` then `up`), and it refuses
    to run without `--yes`.
  - `urls` prints `http://localhost:3000` plus one `http://<ip>:3000` per address from
    `hostname -I`.
  - It operates on the `bountyhub` project only; no prune, no pattern-based stop/rm.
- **`scripts/smoke_test.py`** — Python 3 standard library only (no pip installs, no `jq`).
  It checks a running instance the way the UI uses it and exits 0 only if every check
  passes, printing one `PASS`/`FAIL` line per check.
  - `--frontend-url` (default `http://localhost:3000`): API calls go through
    `/api/backend/*`, login goes through the UI's own route (`/api/auth/login`), and the
    `/login` page and the dashboard redirect for a signed-out visitor are checked too.
    `--backend-url` talks to FastAPI directly and runs the API checks only.
  - Credentials come from `--email` / `--password` or `SMOKE_EMAIL` / `SMOKE_PASSWORD`.
    The app is single-user, so `403 Registration is closed` on register is not a failure:
    the script goes on to log in with the given credentials.
  - Checks: `GET /auth/status` returns a boolean `registration_open` (and `false` after
    the register/login step) → in frontend mode `/register` answers 200 or redirects to
    `/login` → register or login → the login response sets the session cookie without
    the `Secure` attribute when the URL is `http://` → `/auth/me` → create a program →
    add `in` scope rules →
    `scope-check` accepts an in-scope host and rejects another → `GET /settings/ai` →
    `POST /recon/scans` with only out-of-scope targets returns 422 with
    `rejected_targets` → a request without the cookie returns 401.
  - After login it also checks `GET /dashboard/summary` (200, integer `programs`) and
    `GET /recon/scans` (200, a list), and in frontend mode that `/settings` answers 200
    with the session cookie.
  - It never submits a scan that could be accepted, and every hostname it uses is under
    the reserved `.invalid` TLD, so no real host can be reached even if a check is wrong.
  - It deletes the program it created, and never prints the password or the cookie. It
    cannot delete the user it registered; on a fresh stack that is done by `reset`.
