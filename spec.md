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

Merged on `master` (the default branch — there is no `main`): infra + backend skeleton
(#1), auth (#2), JS crawler + secret scanner adapters (#5), AI triage + settings (#6),
frontend skeleton + auth (#7), frontend feature pages (#8).

**Built but not merged** — this is why #3 and #4 show as blocked:

| Branch | Content | Why it did not land |
|---|---|---|
| `task-3` | Bounty domain (`/programs` + nested scope-rules/targets/findings/notes) and a strict `ScopeValidator` | 16 commits behind `master`; conflicts in `backend/app/main.py` and `backend/app/models/__init__.py` (router/model registration). |
| `task-4` | Subfinder/httpx adapters, `ReconService`, ARQ job, `/recon/scans` endpoints | Branched before the skeleton existed. Conflicts in 7 files and it ships its own `app/db.py`, `models/base.py`, `recon/base.py`, `recon/scope.py`, `ReconAsset` model. Needs a **port**, not a rebase. |

Known gaps on `master` that the remaining backlog closes:
- Three different `ScopeValidator` implementations exist (`master:app/recon/scope.py`,
  `task-3:app/services/scope_validator.py`, `task-4:app/recon/scope.py`). The one on
  `master` matches `url` rules with a raw string prefix, so a rule `https://example.com`
  also accepts `https://example.com.evil.net`. It must be replaced, not kept.
- Only `/auth/me` checks the auth cookie; `/settings/ai` and `/triage` are open.
- `backend/alembic/versions/` is empty, but the backend container runs
  `alembic upgrade head` — in Docker no tables are created.
- `infra/Dockerfile.worker` does not install subfinder/httpx; `app/worker.py` registers no
  recon job.
- There is no real HTTP `Fetcher` for the JS crawler / secret scanner (tests use a fake).
- The frontend already calls `/programs…` and `/recon/scans…`; those routes 404 today.

## 4. Architecture

Monorepo, two apps + infra:

```
/backend      FastAPI (Python 3.12), OOP service layer, SQLAlchemy 2.x, Alembic
/frontend     Next.js (App Router, TS), Tailwind, shadcn/ui, feature-based folders
/infra        docker-compose.yml, worker Dockerfile with recon tools
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
- **Dev up:** `docker compose -f infra/docker-compose.yml up --build`
  (backend applies Alembic migrations on start).
- **Backend tests:** `cd backend && pip install -r requirements.txt -r requirements-dev.txt
  && pytest` (SQLite + fakes; subprocess runner, fetcher and AI providers are mocked —
  no real network/tool calls in tests).
- **Backend lint:** `cd backend && ruff check .`
- **Frontend tests:** `cd frontend && npm ci && npm test` (Vitest).
- **Frontend lint/build:** `npm run lint`, `npm run build`.
- All merges must keep both suites green and must not make real external calls in tests.

## 7. Conventions
- Backend OOP service/repository layering; no business logic in routers.
- Recon adapters never bypass `ScopeValidator`; scope matching lives in one module.
- Every router except health and auth login/register depends on `get_current_user`.
- Secrets/tokens stored only in the `settings` table (local), never logged or returned.
- **Integration workflow:** tasks are done one at a time, in backlog order. Branch from
  the current `master`; before handing in, merge `master` into the branch and re-run the
  tests. `backend/app/main.py`, `backend/app/models/__init__.py` and
  `backend/requirements.txt` are shared registration files — add lines, never rewrite
  them. Do not delete the `task-3` / `task-4` branches or their worktrees.
