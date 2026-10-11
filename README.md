# BountyHub

Single-user, self-hosted workspace for bug-bounty work: programs, scope, findings and
notes, plus AI-assisted reconnaissance (subfinder → httpx → JS crawl → secret scan →
AI triage). Recon only ever runs against assets you have marked **in scope**.

Use it only against targets you are explicitly authorized to test.

## First run (Parrot OS)

Prerequisites: Docker with the Compose plugin, **or** podman with `docker-compose`
(on Parrot `docker` may be podman's Docker-compatible CLI; the script handles both).
You do not need to create any config by hand.

1. **Start the stack** from the repository root:

   ```bash
   scripts/stack.sh up
   ```

   This is the same as running Compose by hand:

   ```bash
   docker compose -p bountyhub -f infra/docker-compose.yml --env-file infra/.env up -d --build
   ```

   The first run creates `infra/.env` with generated secrets (mode 600) if it is
   missing and never overwrites an existing one; keep it, because the Postgres volume
   is initialised with that password. The first build takes a few minutes (the worker
   image downloads pinned `subfinder` and `pd-httpx` binaries); the backend applies
   Alembic migrations on start. Five services come up: `postgres`, `redis`, `backend`,
   `worker`, `frontend`.

   **podman:** on Parrot `docker` is podman's Docker-compatible CLI with
   `docker-compose` as the compose provider. Compose needs the podman API socket;
   `scripts/stack.sh` starts it for you, or do it by hand:

   ```bash
   systemctl --user start podman.socket
   export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
   ```

   The compose file uses fully qualified `docker.io/library/...` images, so it works
   on both podman and Docker. The harmless "Emulate Docker CLI using podman" notice
   can be silenced with `sudo touch /etc/containers/nodocker`.

2. **Browse** the app at <http://localhost:3000>, or `http://<laptop-ip>:3000` from
   another machine on the LAN (`hostname -I` or `scripts/stack.sh urls` lists the
   addresses). The API is published on `localhost:8000` (`127.0.0.1` only) for
   debugging; the browser itself only talks to `:3000`, which proxies API calls
   under `/api/backend/*`. Postgres and Redis are not published.

   Verified on Parrot: `curl -fI http://<laptop-ip>:3000` answers (307 to `/login`)
   with no firewall changes. If another machine still cannot connect, a host
   firewall is probably blocking port 3000; allow it with your firewall tool (for
   example `sudo ufw allow 3000/tcp`).

   Day-to-day commands (always with `-p bountyhub`, or use `scripts/stack.sh`):

   ```bash
   docker compose -p bountyhub ps                 # status, all five should be healthy
   docker compose -p bountyhub logs -f [service]  # follow logs
   docker compose -p bountyhub down               # stop; the database volume is kept
   docker compose -p bountyhub down -v            # also DELETE the database volume
   ```

   `scripts/stack.sh ps|logs|down|restart` wrap these. `scripts/stack.sh reset --yes`
   runs `down -v` and then `up`: it **destroys the database** (all programs, findings
   and the registered user) and starts empty. It refuses to run without `--yes`.

   After a reboot the containers are not running; start the stack again with
   `scripts/stack.sh up` (data in the volume is still there).

   `python3 scripts/smoke_test.py` runs a repeatable end-to-end check of a running
   instance (register/login, scope check, rejected scan, 401 without a cookie).

3. **Register the single user** at <http://localhost:3000>. The first visit lands on
   the create-account page (`/register`); enter an email and a password of at least 8
   characters, and you are signed in straight away. Once the account exists,
   registration is closed and the same URL shows the sign-in page instead. All other
   backend routes require the login cookie.
4. **Create a program** and add **scope rules** (see below). Add the targets you want
   to scan.
5. **Configure AI triage in Settings**, either:
   - **Claude:** run `claude setup-token` on your machine and paste the token; or
   - **OpenAI-compatible:** enter the base URL and API key.
6. **Start a scan** from the program's Recon page. Targets that fail the scope check are
   rejected before any tool runs; progress and results are polled from the job.

## Public access (Cloudflare Tunnel)

To reach the app from outside your LAN, run `cloudflared` as part of the stack. It makes an
outbound connection to Cloudflare and forwards to `http://frontend:3000`; no router port
is opened. The tunnel container sits on its own `edge` network and cannot reach the
backend, Postgres or Redis.

`scripts/stack.sh tunnel up` refuses to start unless your account is already registered
(the backend must answer `registration_open: false`), so a stranger can never claim the
first account. Register at <http://localhost:3000> first.

### Quick tunnel (no account needed)

```bash
scripts/stack.sh tunnel up      # prints https://<random-words>.trycloudflare.com
scripts/stack.sh tunnel url     # print it again
scripts/stack.sh tunnel status
scripts/stack.sh tunnel down    # back to LAN mode
```

The URL is new every time the tunnel container starts, and Cloudflare gives quick
tunnels no uptime guarantee. Cloudflare Access cannot be put in front of a quick tunnel,
so the app's own login is the only gate.

### Named tunnel with Cloudflare Access (recommended)

1. In the Cloudflare Zero Trust dashboard, open **Networks → Tunnels → Create a tunnel**
   (type *Cloudflared*), name it, and copy the **token** from the install command.
2. Add a **public hostname** to the tunnel, e.g. `hub.example.com`, with service type
   `HTTP` and URL `frontend:3000`. The domain must be on your Cloudflare account.
3. Put the token and hostname in `infra/.env`:

   ```
   TUNNEL_TOKEN=<token>
   PUBLIC_HOSTNAME=hub.example.com
   ```

4. Under **Access → Applications**, add a *Self-hosted* application for the same
   hostname, with a policy that allows only your email address and the *One-time PIN*
   login method. Cloudflare then asks for an emailed code before anything reaches the app.
5. Run `scripts/stack.sh tunnel up`. It prints `https://hub.example.com`.

### What tunnel mode changes

Tunnel mode is the `BOUNTYHUB_TUNNEL=on|off` line in `infra/.env`, which `tunnel up` and
`tunnel down` edit (nothing else in the file is touched). While it is on, every
`scripts/stack.sh` command:

- starts the tunnel service (`tunnel-named` if `TUNNEL_TOKEN` is set, else `tunnel-quick`);
- publishes the frontend on `127.0.0.1:3000` only, so `http://<lan-ip>:3000` stops
  working; use the public URL, or `http://localhost:3000` on the laptop;
- sets `AUTH_COOKIE_SECURE=true`, so the login cookie is only sent over HTTPS (it does not
  work over plain `http://localhost` in this mode, use the public URL).

`scripts/stack.sh urls` shows the public URL while the tunnel is on.

### After a reboot

Containers do not restart by themselves under podman. `scripts/stack.sh up` brings the
stack back with the tunnel (the mode is stored in `infra/.env`). A quick tunnel gets a
new URL; a named tunnel keeps its hostname.

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
