# BountyHub — Backlog

Ordered. Each task is independently implementable (~15 tool turns incl. tests).
Work them **one at a time, in order** — each branches from the current `master`.

## Done
1. Infra & backend skeleton
2. Auth (backend)
5. JS endpoint crawler + secret/leak scanner adapters (backend)
6. AI triage provider layer (backend)
7. Frontend skeleton + auth (Next.js)
8. Frontend feature pages: programs/findings/notes + recon dashboard (Next.js)

## Superseded
3. Bounty domain + ScopeValidator — code exists on branch `task-3`, never merged
   (conflicts in `main.py`, `models/__init__.py`). Replaced by tasks 9–10.
4. Recon pipeline — code exists on branch `task-4`, never merged (branched before the
   skeleton, conflicts in 7 files, duplicate db/base/scope modules). Replaced by
   tasks 12–13.

## Open

### 9. Land the bounty domain from `task-3` onto master
Bring branch `task-3` (programs, scope_rules, targets, findings, notes: models, schemas,
repository, services, `app/api/bounty.py`, tests) onto current `master`. Merge `master`
into the branch and resolve the two conflicts by keeping **both** sides: `main.py` must
register health, auth, settings, triage and bounty routers; `models/__init__.py` must
export `ReconAsset`, `Setting`, `User` and the bounty models. Keep
`app/services/scope_validator.py` as is for now (task 10 moves it). Check the routes
match `frontend/src/lib/api.ts` (`/programs`, nested `scope-rules|targets|findings|notes`,
`scope-check`). Done when `cd backend && pytest` and `ruff check .` pass on the result.

### 10. One ScopeValidator: replace the loose one with the strict one
Move the strict validator from `app/services/scope_validator.py` to `app/recon/scope.py`,
replacing the implementation there, and delete the old module. Update `ProgramService`,
`JSEndpointCrawler`, `SecretScanner` and their tests to the single API
(`check`, `is_in_scope`, `partition`; rules read as `action`/`type`/`value`). Keep the
semantics in spec §4. Add regression tests: a `url` rule `https://example.com` rejects
`https://example.com.evil.net`; an `out` rule beats a matching wildcard; `*.example.com`
does not match the apex; empty rule set rejects everything; garbage input is rejected.
Done when no other module defines scope matching (`grep -rn "class ScopeValidator"`
returns one hit) and the backend suite is green.

### 11. Require auth on every backend route
Add `Depends(get_current_user)` at router level to bounty, settings and triage routers
(everything except `/health`, `/auth/register`, `/auth/login`). Add a test that walks
`app.routes` and asserts every non-exempt route returns 401 without the cookie, so any
router added later fails the suite if it is left open. Give the existing API tests an
authenticated-client fixture in `tests/conftest.py`.

### 12. Recon adapters for Subfinder and httpx + recon job model
Port from branch `task-4` onto master's structure (do not merge the branch). Add
`CommandRunner` protocol + `SubprocessRunner` (argv list, timeout, no shell) to
`app/recon/`, and `SubfinderTool` / `HttpxTool` implementing master's synchronous
`ReconTool.run(targets) -> list[ReconAssetResult]` (subfinder → `SUBDOMAIN`, httpx JSON
lines → `HOST` with status/title/tech in metadata). Binary paths come from settings
(`subfinder`, `pd-httpx`). Add the `ReconJob` model and extend the existing `ReconAsset`
model with `source` and a FK to `recon_jobs` (keep `ai_score`/`ai_label`/`ai_reason`);
add `ReconJobRepository` and extend `ReconAssetRepository`. Use
`app.core.database` / `app.models.base` — no `app/db.py`. Tests use a fake runner with
fixture output and cover parsing, tool-missing and timeout errors.

### 13. ReconService, ARQ job and scan endpoints
`ReconService` (spec §4): `create_job(program_id, targets)` partitions targets with
`ScopeValidator` and raises when none are in scope; `run_job(job_id)` re-loads the
rules, runs subfinder → httpx, re-validates discovered hosts before httpx, stores
assets, tracks `status`/`current_stage`/`rejected_targets`/`error`. ARQ function
`run_recon_job` in `app/jobs/recon_jobs.py`, registered in `app/worker.py`; ARQ pool
created on app startup. Router `app/api/recon.py`: `POST /recon/scans` (202, or 422 with
`rejected_targets`), `GET /recon/scans/{id}`, `GET /recon/scans/{id}/assets`, with
response fields named as in `frontend/src/lib/types.ts`. Tests use fake tools and a fake
queue and assert that an out-of-scope target, and an out-of-scope host returned by
subfinder, are never passed to any tool.

### 14. Complete the pipeline: JS crawl, secret scan, AI triage
Add a real `Fetcher` (timeout, response size cap, redirect target re-validated against
scope, errors return `None`). Extend `ReconService.run_job` with the `js_crawler` and
`secret_scanner` stages over the live in-scope hosts, then a best-effort `triage` stage
calling `AITriageService` on the job's assets (provider failure or no provider
configured is noted on the job, scan still completes). Secret values are stored but
never logged. Tests use a fake fetcher and fake provider: stage order, assets of all
four types stored for one job, triage failure does not fail the job.

### 15. Delivery: migrations, worker image, env and README
Initial Alembic migration covering every table in `Base.metadata` plus a test that
`alembic upgrade head` on an empty SQLite DB yields the same tables as the models.
`infra/Dockerfile.worker`: install pinned ProjectDiscovery subfinder and httpx release
binaries (httpx as `/usr/local/bin/pd-httpx`). `infra/docker-compose.yml`: pass
`JWT`/secret settings from an env file; add `infra/.env.example`. Root `README.md`:
first run on Parrot OS (compose up, register the single user, add a program and scope
rules, paste the `claude setup-token` token or OpenAI-compatible key in Settings, start
a scan) and how to run the tests. Verify with `docker compose -f infra/docker-compose.yml config`.

### 16. Final verification on master
With 9–15 merged: run `pytest` + `ruff check .` in `backend/`, and `npm test`,
`npm run lint`, `npm run build` in `frontend/`. Diff the backend response schemas against
`frontend/src/lib/types.ts` and `frontend/src/lib/api.ts` and fix any mismatch in field
names, enums or paths. Fix whatever fails; report the commands and their results. Leave
the `task-3` / `task-4` branches and worktrees in place.
