# BountyHub

Single-user, self-hosted workspace for bug-bounty work: programs, scope, findings and
notes, plus AI-assisted reconnaissance (subfinder → httpx → JS crawl → secret scan →
AI triage). Recon only ever runs against assets you have marked **in scope**.

Use it only against targets you are explicitly authorized to test.

## First run (Parrot OS)

Prerequisites: Docker with the Compose plugin, **or** podman with `docker-compose`
(on Parrot `docker` may be podman's Docker-compatible CLI; the script handles both).
You do not need to create any config by hand.

1. **Start the stack** from any directory:

   ```bash
   scripts/stack.sh up
   ```

   The first run creates `infra/.env` with generated secrets (mode 600) if it is
   missing and never overwrites an existing one; keep it, because the Postgres volume
   is initialised with that password. On podman the script also starts your user's
   `podman.socket` and sets `DOCKER_HOST`. The backend applies Alembic migrations on
   start; the worker image ships pinned `subfinder` and `pd-httpx` binaries.

2. **Browse** <http://localhost:3000>, or `http://<laptop-ip>:3000` from another
   machine on the LAN (`scripts/stack.sh urls` lists the addresses). The API is
   published on `127.0.0.1:8000` only; the browser reaches it through the frontend.

   Day-to-day commands:

   ```bash
   scripts/stack.sh ps            # container status
   scripts/stack.sh logs [svc]    # follow logs, optionally for one service
   scripts/stack.sh restart
   scripts/stack.sh down          # stop; the database volume is kept
   ```

   `scripts/stack.sh reset --yes` runs `down -v` and then `up`: it **destroys the
   database** (all programs, findings and the registered user) and starts empty.
   It refuses to run without `--yes`.

   After a reboot the containers are not running; start the stack again with
   `scripts/stack.sh up` (data in the volume is still there).

3. **Register the single user** at <http://localhost:3000> (register page). All other
   backend routes require the login cookie.
4. **Create a program** and add **scope rules** (see below). Add the targets you want
   to scan.
5. **Configure AI triage in Settings**, either:
   - **Claude:** run `claude setup-token` on your machine and paste the token; or
   - **OpenAI-compatible:** enter the base URL and API key.
6. **Start a scan** from the program's Recon page. Targets that fail the scope check are
   rejected before any tool runs; progress and results are polled from the job.

## Scope rules

Each program has `in` and `out` rules of type `domain`, `wildcard`, `ip` or `url`.
The scope guard is fail-closed and enforced server-side before every pipeline stage,
including on hosts discovered by earlier stages.

- An `out` rule always wins over any `in` rule.
- No matching `in` rule means rejected; an empty rule set rejects everything.
- Unparseable targets or rules never match.
- `domain` — exact host only: `example.com` does not cover `sub.example.com`.
- `wildcard` — `*.example.com` covers subdomains at any depth but **not** the apex.
  Add a `domain` rule to scan the apex.
- `ip` — a single IP or CIDR; matches IP-literal targets only.
- `url` — host match plus a path prefix on a segment boundary, never a raw string
  prefix (`https://example.com` does not match `https://example.com.evil.net`).

## Tests

```bash
# backend (SQLite + fakes; no network or real tools)
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest
ruff check .

# frontend
cd frontend
npm ci
npm test          # Vitest
npm run lint
npm run build
```

## Layout

```
backend/   FastAPI, SQLAlchemy, Alembic migrations (backend/alembic/versions)
frontend/  Next.js App Router
infra/     docker-compose.yml, Dockerfile.worker, .env.example
```
