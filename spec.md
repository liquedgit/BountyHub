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
  are rejected and never passed to a subprocess.
- The scope check is enforced server-side in the job layer, not just in the UI.
- This is a tool for the user's own authorized engagements; the scope guard exists to keep
  activity within the programs' stated rules.

## 2. Scope (MVP)

In:
- Email+password auth (single user), argon2 hashing, JWT in httpOnly cookies, Next.js
  middleware route protection.
- Programs (platform, scope in/out, reward info), Targets, Findings/Reports (status,
  severity, payout), Markdown Notes attached to programs/findings.
- Recon jobs: Subfinder → httpx → JS endpoint crawl → secret/leak scan, run as background
  tasks with status + streamed results.
- AI triage: two interchangeable providers — (a) Claude via `claude setup-token` session
  auth, (b) any OpenAI-compatible API via API key. Provider chosen in settings.
- Docker Compose brings up the whole stack with recon tools installed in the worker image.

Out (future):
- Multi-user/teams, RBAC.
- Scheduled/recurring scans.
- Live WebSocket streaming (MVP uses polling of job status/results).

## 3. Architecture

Monorepo, two apps + infra:

```
/backend      FastAPI (Python 3.12), OOP service layer, SQLAlchemy 2.x, Alembic
/frontend     Next.js (App Router, TS), Tailwind, shadcn/ui, feature-based folders
/infra        docker-compose.yml, worker Dockerfile with recon tools
```

### Backend (FastAPI, OOP)
Layered design, dependency-injected:
- **API layer** (`app/api/`): routers per feature (auth, programs, targets, findings,
  notes, recon, settings). Thin — validate, delegate to services.
- **Service layer** (`app/services/`): business logic as classes
  (`AuthService`, `ProgramService`, `ReconService`, `AITriageService`, …).
- **Repository layer** (`app/repositories/`): DB access classes wrapping SQLAlchemy.
- **Domain/models** (`app/models/` SQLAlchemy, `app/schemas/` Pydantic).
- **Recon tool adapters** (`app/recon/`): one class per tool implementing a common
  `ReconTool` interface (`run(targets) -> results`). `ScopeValidator` gates every target.
- **AI providers** (`app/ai/`): `AIProvider` abstract base; `ClaudeProvider` and
  `OpenAICompatibleProvider` concrete implementations, selected by a factory from settings.
- **Jobs** (`app/jobs/` via ARQ + Redis): recon pipeline runs as background tasks writing
  progress/results to Postgres.

### Frontend (Next.js)
- App Router, TS, server components for data fetch, client components for interactivity.
- `components/ui` (shadcn), `components/<feature>`, `app/(dashboard)/<feature>` routes.
- Dark mode, dashboard overview, feature pages for programs/findings/recon/notes.
- Auth via httpOnly cookie; middleware guards `(dashboard)` routes.

### Data model (core tables)
`users`, `programs`, `scope_rules` (in/out, type: domain/wildcard/ip/url),
`targets`, `recon_jobs`, `recon_assets` (subdomains/hosts/endpoints/secrets with metadata
+ AI triage score), `findings`, `notes`, `settings`.

## 4. Tech stack
- Backend: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, ARQ, Redis, argon2-cffi,
  python-jose (JWT), pytest + httpx test client.
- Frontend: Next.js 14+, TypeScript, Tailwind, shadcn/ui, React Query, Vitest + RTL.
- Recon: subfinder, httpx (ProjectDiscovery) binaries in worker image; JS crawler and
  secret scanner implemented as adapter classes shelling out / parsing.
- Infra: Docker Compose (postgres, redis, backend, worker, frontend).

## 5. Running & tests
- **Dev up:** `docker compose -f infra/docker-compose.yml up --build`
- **Backend tests:** `cd backend && pytest` (uses SQLite/ephemeral Postgres + fakeredis;
  recon adapters and AI providers are mocked — no real network/tool calls in tests).
- **Frontend tests:** `cd frontend && npm test` (Vitest).
- **Lint:** backend `ruff`, frontend `eslint`.
- All PRs must keep tests green and must not make real external network calls in tests.

## 6. Conventions
- Backend OOP service/repository layering; no business logic in routers.
- Recon adapters never bypass `ScopeValidator`.
- Secrets/tokens stored only in `settings` table (local), never logged.
