# BountyHub — Backlog

Ordered. Each task is independently implementable (~15 tool turns incl. tests).
Earlier tasks lay foundations later ones build on.

## 1. Infra & backend skeleton
Scaffold the monorepo and Docker Compose. `backend/` FastAPI app with layered folders
(`api/`, `services/`, `repositories/`, `models/`, `schemas/`), config via env, SQLAlchemy
+ Alembic wired to Postgres, Redis connection, health endpoint. `docker-compose.yml` with
postgres/redis/backend/worker/frontend services and a worker Dockerfile stub.
Pytest configured with an ephemeral DB and a passing health-check test.

## 2. Auth (backend)
AuthService + repository: register-once/login, argon2 hashing, JWT issued into httpOnly
cookie, `get_current_user` dependency, logout. Routers thin. Unit tests for hashing,
token issue/verify, and protected-route rejection (mocked DB).

## 3. Bounty domain: programs, scope, targets, findings, notes (backend)
Models + Pydantic schemas + repositories + services + CRUD routers for programs,
scope_rules (in/out), targets, findings (status/severity/payout), markdown notes.
Tests for CRUD and for the `ScopeValidator` class (given scope rules, correctly
accepts in-scope and rejects out-of-scope/excluded hosts).

## 4. Recon pipeline: adapters, scope gate, background jobs (backend)
`ReconTool` interface + adapter classes for Subfinder and httpx (subprocess wrappers,
output parsed to `recon_assets`). `ReconService` orchestrates the pipeline and calls
`ScopeValidator` on every target before any subprocess runs. ARQ job + `recon_jobs`
status tracking + endpoints to start a scan and poll status/results. Tests mock the
subprocess layer and assert out-of-scope targets are never executed.

## 5. JS endpoint crawler + secret/leak scanner adapters (backend)
Two more adapter classes implementing `ReconTool`: a JS/SPA endpoint extractor (parses
JS for API routes/endpoints/source maps) and a secret/leak scanner (regex/entropy rules
for keys, tokens, exposed `.env`/config). Results stored as `recon_assets` typed
endpoint/secret. Both gated by `ScopeValidator`. Tests use fixture inputs (no network).

## 6. AI triage provider layer (backend)
`AIProvider` abstract base + `ClaudeProvider` (claude setup-token session auth) and
`OpenAICompatibleProvider` (base-url + API key), plus a factory selecting from settings.
`AITriageService` scores/ranks recon_assets and flags likely secrets vs false positives.
Settings endpoints to choose provider and store credentials locally. Tests mock both
providers (no real API calls) and assert the factory + triage wiring.

## 7. Frontend skeleton + auth (Next.js)
App Router + TS + Tailwind + shadcn/ui setup, dark mode, dashboard layout shell with
feature-based folders, login page, httpOnly-cookie auth flow, and middleware guarding
`(dashboard)` routes. React Query client configured against the backend. Vitest + RTL
test for the login form and a guarded-route redirect.

## 8. Frontend feature pages: programs/findings/notes + recon dashboard (Next.js)
Feature components and pages: programs list/detail (with scope editor), findings board
(status/severity/payout), markdown notes editor, and a recon page to launch a scan,
poll job status, and view triaged assets (subdomains/hosts/endpoints/secrets) with AI
scores. Component tests for the key views (mocked API).
