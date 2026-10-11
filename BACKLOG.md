# BountyHub — Backlog

The user said "push it": publish `main` (the UI pass and the tunnel round, 48 commits
ahead of `origin/main`) to the **public** repo `github.com/liquedgit/BountyHub`. The rules
are spec §8 "GitHub" and §7.

```
1  audit the unpushed range, push main ──► 2  check the public repo from a fresh clone,
                                               check the tunnel, report the URL
```

2 waits for 1. Two tasks are all this needs; the work is one push and one independent
check of it.

Rules for both tasks:
- **The running instance holds the user's account.** Never register, sign in or send a
  login (right or wrong) to it, on localhost or on the public URL. Signed-out `GET`s only.
- Never `up`, `down`, `restart`, `build` or `reset` the `bountyhub` stack and never
  restart the tunnel: recreating the tunnel container changes the public URL.
- Never print, copy or commit a value from `infra/.env`. Compare by pattern file
  (`grep -f`), not by echoing the value.
- Plain fast-forward push of `main` only. No `--force`, no history rewriting, no tags, no
  `task-*` branches, no change to the GitHub repo's settings or visibility.
- The public tunnel URL goes in the task report only, never in a tracked file.

## Done
1–16. Backend, recon pipeline, AI triage, first frontend, migrations, worker image.
17–26. Published to GitHub as `main`, stack running, operator scripts, sign-up/sign-in.
27–35. UI and behaviour pass, rebuilt and verified.
36–42. Hardening, cloudflared service, security test list, deployed on a quick tunnel.

## Open — publish to GitHub

### 1. Audit the unpushed commits and push `main` to GitHub
Work in the main checkout on `main` (this task pushes the `main` ref itself, so nothing
may be left on a side branch).
1. `git fetch origin`. `git rev-list --count main..origin/main` must be 0 (fast-forward).
   If it is not, stop and report; do not merge or rebase on your own.
2. If `spec.md` or `BACKLOG.md` are modified in the main checkout, commit exactly those
   two files on `main` (`docs: spec and backlog for the publish round`). Anything else
   uncommitted: leave it, do not push it, report it.
3. Audit `origin/main..main` as in spec §8 "Before every push": `git diff origin/main..main`
   and `git log -p origin/main..main` (a secret added and later removed is still
   published), plus `git ls-files`. Search for: private-key headers, `sk-ant-`, `sk-`
   followed by 20+ characters, `eyJ…\.eyJ…` JWTs, `ghp_`/`gho_`/`github_pat_`,
   `TUNNEL_TOKEN=`/`JWT_SECRET=`/`POSTGRES_PASSWORD=`/`DATABASE_URL=` with a non-placeholder
   value, each value of `infra/.env` (pattern file, values never shown), any
   `<name>.trycloudflare.com` host, the user's email, the laptop's hostname and its
   LAN/public IP addresses. Tracked files named `.env`, `*.pem`, `*.key` must not exist.
   Look at `docs/SECURITY_TESTS.md` by eye: it records command output from this laptop.
4. Classify every hit. Expected: sentinels in `backend/tests`, `frontend/tests` and
   `scripts/security_check.py`, placeholders in `infra/.env.example`, documentation
   ranges (`127.0.0.1`, `169.254.169.254`, `10.0.0.5`, `*.invalid`, `example.com`).
   **A real secret or the public URL in any commit of the range: do not push.** Report
   the file and commit (not the value) and stop; the fix needs the user's decision.
5. `git push origin main`. Then `git fetch origin` and confirm
   `git rev-parse main` = `git rev-parse origin/main` and
   `gh api repos/liquedgit/BountyHub/commits/main -q .sha` gives the same sha.

Hand-in: the pushed sha and commit count, the audit commands run, the expected hits by
category, and anything left uncommitted. No test suite is needed: no code changes.

### 2. Check the public repo from a fresh clone, check the tunnel, report  (after 1)
Done by a different engineer than task 1; do not trust its hand-in, repeat the proof.
1. `git clone https://github.com/liquedgit/BountyHub.git` into a new temp directory
   (anonymous clone: use `GIT_TERMINAL_PROMPT=0` and no credential helper, which also
   shows the repo is readable without login). Remove the directory afterwards.
2. In the clone: `HEAD` equals local `main`; no `.env`, `*.pem`, `*.key` file; the
   pattern search of task 1 step 3 over the checked-out tree and over
   `git log -p --all` is clean apart from the expected categories; only `main` exists
   on the remote (`git ls-remote --heads origin`).
3. The clone is what a stranger gets, so it must be usable: `infra/.env.example`,
   `scripts/stack.sh`, `scripts/security_check.py`, `docs/SECURITY_TESTS.md` and every
   file the README links to exist; `bash -n scripts/stack.sh`;
   `BOUNTYHUB_ENV_FILE=<temp copy of .env.example> scripts/stack.sh config` renders
   (config only, nothing is started). A README link to a missing file is fixed with a
   normal commit on a branch; say in the hand-in that this fix is **not** pushed.
4. The deployment, read-only: `scripts/stack.sh ps` (six services up),
   `scripts/stack.sh tunnel status`, `scripts/stack.sh tunnel url`; on the public URL
   `GET /login` → 200, `GET /api/backend/auth/status` → `registration_open: false`,
   `GET /api/backend/docs` → 404, `GET /api/backend/programs` → 401; then
   `python3 scripts/security_check.py --mode signed-out` against the public URL.
5. Report: the GitHub commit URL, the current public URL, the local URL, what was
   checked and what failed, and the standing limits: the quick-tunnel URL changes when
   the tunnel is recreated or the laptop reboots, AUTH-5 on the live URL is still not
   run, and a fixed domain needs a named tunnel (`TUNNEL_TOKEN`, README "Public access").
