# BountyHub — Backlog

Each task is independently implementable (~15 tool turns incl. tests) and branches from
`main`. Two lanes run at the same time (spec §8 "Working in parallel on one host"):

```
stack lane (one at a time, owns the running stack):   18 ──► 19 ──► 20
script lane (no running stack needed, start now):     21
                                                      22
```

21 and 22 are independent of each other and of 18. 19 uses their output if it is already
on `main`, and does the same steps by hand if it is not.

## Done
1–2, 5–8. Skeleton, auth, JS crawler + secret scanner, AI triage, frontend.
3–4. Superseded by 9–10 and 12–13 (original branches never merged).
9. Bounty domain landed · 10. Single strict ScopeValidator · 11. Auth on every route ·
12. Subfinder/httpx adapters + recon job model · 13. ReconService, ARQ job, scan endpoints ·
14. JS crawl, secret scan, AI triage stages · 15. Migration, worker image, env example,
README · 16. Final verification · 17. Published to GitHub as `main`.

## Open — stack lane

### 18. Get the stack building and healthy in Docker  (in progress)
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

If 21 / 22 are on `main` when this starts, merge `main` first and use them instead of
doing the steps by hand: `python3 scripts/smoke_test.py` for the API and page checks,
`scripts/stack.sh urls` for the addresses and `scripts/stack.sh reset --yes` for the
wipe. Fix the script, not the check, only when the script itself is wrong; a real app
bug still gets a fix and a regression test. Correct the README run guide from 22 where
the live stack differs from it.

### 20. Push the deployment fixes to GitHub  (after 19)
With 18–19 (and 21–22 if finished) merged into `main`: confirm the tree is clean and
`infra/.env` is untracked, `git push origin main` (fast-forward only), and check
`git ls-remote origin main` equals local `main`. Confirm the `bountyhub` stack is still
up and healthy and report the final URLs and the repository link.

## Open — script lane (parallel with 18, start now)

Rules for both (spec §8 "Working in parallel on one host"): do not run `up`, `down`,
`build` or any volume command against the `bountyhub` project — task 18 is using it.
Do not edit `infra/docker-compose.yml` or any Dockerfile. Do not create or overwrite the
main checkout's `infra/.env`. Do not push.

### 21. `scripts/smoke_test.py` — repeatable end-to-end check
Read spec §8 "Operator scripts" for the contract. Python 3 standard library only
(`urllib`, `http.cookiejar`, `argparse`, `json`). Before writing, read
`frontend/src/lib/` and `frontend/src/app/api/auth/login/route.ts` to see which paths the
UI really calls, and `backend/app/api/` for the request/response shapes.
- Modes: `--frontend-url` (default `http://localhost:3000`) or `--backend-url`.
- Credentials from `--email` / `--password` or `SMOKE_EMAIL` / `SMOKE_PASSWORD`; treat
  `403` on register as "already registered" and continue to login.
- Run the checks listed in the spec, one `PASS`/`FAIL` line each, exit 0 only when all
  pass, non-zero with a clear message when the server is unreachable.
- Every hostname used is under `.invalid` (for example rule `in.bountyhub.invalid`,
  rejected host `out.bountyhub.invalid`). The only scan request sends out-of-scope
  targets and must get 422; if it is ever accepted, report FAIL and stop.
- Delete the program the script created, also when a later check fails. Never print the
  password or cookie.

Verify without Docker: in a venv inside your worktree, start the backend on SQLite on
`127.0.0.1` and a spare port (not 3000 / 8000 / 5432) with a throwaway `JWT_SECRET`,
create the tables the way the tests or Alembic do, and run the script with
`--backend-url`. It must pass on a fresh DB, pass again on a second run (registration
closed), and exit non-zero against a closed port. Stop the server afterwards. Put the
exact commands you used in the script's module docstring. `ruff check scripts/` with the
backend config and the backend test suite stay green. `--frontend-url` mode cannot be
run here; keep its extra checks small and say in the hand-in that it is untested until
task 19.

### 22. `scripts/stack.sh` and the README run guide
Read spec §8 ("Running on the user's laptop", "Operator scripts"). Write a POSIX-friendly
bash script (`set -euo pipefail`) with the subcommands and guarantees listed there:
podman detection + `podman.socket` + `DOCKER_HOST`; fixed compose file, project name and
env file resolved from the script's own path; `BOUNTYHUB_ENV_FILE` override; env file
created from `infra/.env.example` with `openssl rand -hex 32` secrets only when missing,
mode 600, nothing secret echoed; `down` without `-v`; `reset` refusing without `--yes`;
`urls` from `hostname -I`; unknown subcommand prints usage and exits 2.

Verify without touching the stack: `bash -n`, `shellcheck` if installed, `stack.sh urls`,
`stack.sh ps` (read-only), and `BOUNTYHUB_ENV_FILE=$(mktemp -u) stack.sh config` to prove
the env file is created once with mode 600, is not overwritten on a second run, and that
compose accepts it. Do **not** run `up`, `down`, `restart` or `reset`; say so in the
hand-in. Remove the temp file.

Then rewrite the README "First run (Parrot OS)" section around the script: prerequisites
(Docker or podman with docker-compose), `scripts/stack.sh up`, where to browse
(`http://localhost:3000`, or `http://<laptop-ip>:3000` from another machine; the API is
on `127.0.0.1:8000` only), `logs` / `ps` / `down`, what `reset --yes` destroys, and that
after a reboot the stack is started again with `scripts/stack.sh up`. Keep the existing
register / program / AI settings / scan steps and every other README section unchanged.
