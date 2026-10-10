# BountyHub — Backlog

Ordered. Each task is independently implementable (~15 tool turns incl. tests).
Work them in order; each branches from the default branch (`main` after task 17).

## Done
1–2, 5–8. Skeleton, auth, JS crawler + secret scanner, AI triage, frontend.
3–4. Superseded by 9–10 and 12–13 (original branches never merged).
9. Bounty domain landed · 10. Single strict ScopeValidator · 11. Auth on every route ·
12. Subfinder/httpx adapters + recon job model · 13. ReconService, ARQ job, scan endpoints ·
14. JS crawl, secret scan, AI triage stages · 15. Migration, worker image, env example,
README · 16. Final verification.

## Open

### 17. Publish the project to GitHub as `main`
Read spec §8 "GitHub". Before pushing, confirm nothing secret is tracked or in history:
`git ls-files` shows only `*.env.example` env files, and
`git log --all -p | grep -nE "gho_|ghp_|sk-ant-|sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY"`
finds only obvious test fixtures / scanner regexes (inspect each hit; if a real
credential is found, stop and report instead of pushing). Then
`git remote add origin https://github.com/liquedgit/BountyHub.git`,
`git branch -m master main`, `git push -u origin main`. If the push is rejected for
credentials run `gh auth setup-git` and retry; do not use `--force`. Update the
remaining `master` wording in `README.md` if any. Done when `git ls-remote origin main`
equals local `main` and `gh repo view liquedgit/BountyHub --json defaultBranchRef`
reports `main`. Push `main` only.

### 18. Get the stack building and healthy in Docker  (after 17)
Read spec §8 "Running on the user's laptop" first — the host runs podman behind the
`docker` CLI and shares the machine with an unrelated `agent-office` container. Add
`name: bountyhub` to `infra/docker-compose.yml`, publish the backend as
`127.0.0.1:8000:8000`, add `restart: unless-stopped`, and add a backend healthcheck on
`/health` that the frontend waits for. Create the main checkout's `infra/.env` with
generated secrets if it does not exist (never commit or print it). Run
`docker compose -f infra/docker-compose.yml --env-file <main checkout>/infra/.env up -d --build`
and fix whatever breaks (image names, Dockerfiles, migration on real Postgres, worker
start-up, frontend build) with the smallest change, keeping it valid for real Docker.
Done when `docker compose -p bountyhub ps` shows postgres, redis, backend, worker and
frontend running/healthy, `curl -f localhost:8000/health` and `curl -fI localhost:3000`
succeed, the worker log shows ARQ started with `run_recon_job` registered, and
`subfinder -version` + `pd-httpx -version` work inside the worker. Backend and frontend
test suites stay green. Leave the stack running. If Docker cannot run at all for a
reason outside the repo (needs sudo, no socket), report the exact error.

### 19. Smoke-test the running app end to end and document access  (after 18)
Against the running stack, through the frontend origin only
(`http://localhost:3000/api/backend/...`, cookie jar): register → login → `/auth/me` →
create a program → add `in` scope rules → `scope-check` accepts an in-scope host and
rejects an out-of-scope one → `GET /settings/ai` → `POST /recon/scans` with only
out-of-scope targets returns 422 with `rejected_targets` → an unauthenticated request
returns 401. Load `/login` and a dashboard page and confirm they render. Do **not**
start a scan that reaches a real host. Fix any bug found (with a regression test) and
rebuild. Check the app answers on the laptop's LAN address (`hostname -I`) port 3000;
if a host firewall blocks it, report the command the user must run rather than
changing the firewall. Update the README "First run" section to match reality
(podman notes, `up -d`, the URLs, `logs` / `down` commands). Finally remove the test
data so the user registers their own account (`docker compose -p bountyhub down -v`,
then `up -d` again) and confirm all five services are healthy. Report the URLs.

### 20. Push the deployment fixes to GitHub  (after 19)
With 18–19 merged into `main`: confirm the tree is clean and `infra/.env` is untracked,
`git push origin main` (fast-forward only), and check `git ls-remote origin main`
equals local `main`. Confirm the `bountyhub` stack is still up and healthy and report
the final URLs and the repository link.
