# BountyHub

Single-user, self-hosted workspace for bug-bounty work: programs, scope, findings and
notes, plus AI-assisted reconnaissance (subfinder → httpx → JS crawl → secret scan →
AI triage). Recon only ever runs against assets you have marked **in scope**.

Use it only against targets you are explicitly authorized to test.

## First run (Parrot OS)

Prerequisites: Docker with the Compose plugin (`sudo apt install docker.io docker-compose-plugin`
or Docker's own packages) and your user in the `docker` group.

1. **Configure secrets.** Compose reads secrets from `infra/.env` and refuses to start
   without them:

   ```bash
   cp infra/.env.example infra/.env
   # set JWT_SECRET (openssl rand -hex 32) and POSTGRES_PASSWORD
   ```

2. **Start the stack.** The backend applies Alembic migrations on start; the worker
   image ships pinned `subfinder` and `pd-httpx` (ProjectDiscovery httpx) binaries.

   ```bash
   docker compose -f infra/docker-compose.yml config   # optional: validate
   docker compose -f infra/docker-compose.yml up --build
   ```

   Frontend: <http://localhost:3000> · API: <http://localhost:8000> (`/health`).

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
