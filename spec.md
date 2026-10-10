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
  middleware route protection. **Every backend route except `/health`, `/auth/register`
  and `/auth/login` requires the auth cookie.**
- Programs (platform, scope in/out, reward info), Targets, Findings/Reports (status,
  severity, payout), Markdown Notes attached to programs/findings.
- Recon jobs: Subfinder → httpx → JS endpoint crawl → secret/leak scan → AI triage, run as
  background tasks with status + polled results.
- AI triage: two interchangeable providers — (a) Claude via `claude setup-token` session
  auth, (b) any OpenAI-compatible API via API key. Provider chosen in settings.
- Docker Compose brings up the whole stack with recon tools installed in the worker image.

Out (future):
- Multi-user/teams, RBAC.
- Scheduled/recurring scans.
- Live WebSocket streaming (MVP uses polling of job status/results).

## 3. Current state (2026-10-10)

Feature-complete for the MVP. Office tasks #1–#16 are merged: bounty domain, the single
strict `ScopeValidator`, auth on every route, the full recon pipeline (subfinder → httpx →
JS crawl → secret scan → AI triage), the initial Alembic migration, the worker image with
pinned `subfinder` / `pd-httpx`, `infra/.env.example` and the README.

Published (task 17, done): `origin` is `https://github.com/liquedgit/BountyHub.git`, the
default branch is `main`, and local `main` is in sync with `origin/main`.

Open — see §8 and the backlog:
- **Task 18 (in progress)** is starting the stack in Docker for the first time. Until it
  lands, image builds, migrations against real Postgres, the worker and the frontend
  proxy are unverified. While it runs it owns `infra/docker-compose.yml`, the three
  Dockerfiles and the running `bountyhub` compose project.
- **Tasks 21–22 (parallel with 18)** add the operator scripts and the README run guide.
  They need no running stack and touch none of task 18's files.
- **Tasks 19–20 (after 18)** smoke-test the live stack, wipe the test data and push.

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
- `GET/PUT /settings/ai`, `POST /triage`, `/auth/{register,login,logout,me}`, `/health`.
- Field names follow `frontend/src/lib/types.ts`: scope rule `action`/`type`/`value`;
  job `status`, `current_stage`, `targets`, `rejected_targets`, `error`, timestamps;
  asset `asset_type`, `value`, `source`, `meta`, `triage_score`. The backend schema maps
  DB columns (`asset_metadata`, `ai_score`) onto these names.

### Frontend (Next.js)
- App Router, TS, server components for data fetch, client components for interactivity.
- `components/ui` (shadcn), `components/<feature>`, `app/(dashboard)/<feature>` routes.
- Dark mode, dashboard overview, feature pages for programs/findings/recon/notes.
- Auth via httpOnly cookie; middleware guards `(dashboard)` routes. Browser calls go
  through the `/api/backend/*` rewrite so the cookie is same-origin.

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
- Every router except health and auth login/register depends on `get_current_user`.
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
- The stack is left running (`up -d`) with an **empty database** so the user registers
  their own account; any test user created during verification is removed first.

### Working in parallel on one host
There is one laptop, one compose project, one running stack and one Postgres volume, so
parallelism is limited by who may touch them.
- Only one task at a time may run `up`, `down`, `build` or a volume wipe against project
  `bountyhub`: task 18 now, then 19, then 20. These stay in sequence.
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
  - Checks: register or login → `/auth/me` → create a program → add `in` scope rules →
    `scope-check` accepts an in-scope host and rejects another → `GET /settings/ai` →
    `POST /recon/scans` with only out-of-scope targets returns 422 with
    `rejected_targets` → a request without the cookie returns 401.
  - It never submits a scan that could be accepted, and every hostname it uses is under
    the reserved `.invalid` TLD, so no real host can be reached even if a check is wrong.
  - It deletes the program it created, and never prints the password or the cookie. It
    cannot delete the user it registered; on a fresh stack that is done by `reset`.
