#!/usr/bin/env bash
# Drive the BountyHub compose stack (project "bountyhub") by hand.
# Usage: scripts/stack.sh {up|down|restart|ps|logs [service]|config|urls|tunnel up|down|url|status|reset --yes}
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$ROOT/infra/docker-compose.yml"
ENV_EXAMPLE="$ROOT/infra/.env.example"
PROJECT=bountyhub
PORT=3000

# Secrets live in the main checkout's infra/.env (the Postgres volume is initialised
# with that password), even when this script runs from a git worktree.
main_checkout() {
  local common
  if common="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" \
    && [ -n "$common" ]; then
    dirname "$common"
  else
    printf '%s\n' "$ROOT"
  fi
}
ENV_FILE="${BOUNTYHUB_ENV_FILE:-$(main_checkout)/infra/.env}"

usage() {
  cat >&2 <<USAGE
Usage: $(basename "$0") <command>

  up            build and start the stack in the background (up -d --build)
  down          stop and remove containers and network; keeps the database volume
  restart       restart the running services
  ps            list the stack's containers
  logs [svc]    follow logs, optionally for one service
  config        validate and print the resolved compose configuration
  urls          print the addresses the frontend can be browsed at
  tunnel up     expose the app through Cloudflare Tunnel (needs registration closed)
  tunnel down   turn the tunnel off and reopen the LAN address
  tunnel url    print the public URL
  tunnel status show tunnel mode and container state
  reset --yes   DESTROYS the database: down -v, then up
USAGE
  exit 2
}

is_podman() {
  command -v docker >/dev/null 2>&1 || return 1
  docker --version 2>&1 | grep -qi podman
}

setup_runtime() {
  command -v docker >/dev/null 2>&1 || { echo "docker not found in PATH" >&2; exit 1; }
  if is_podman; then
    systemctl --user start podman.socket
    export DOCKER_HOST="unix://${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/podman/podman.sock"
  fi
}

ensure_env_file() {
  [ -e "$ENV_FILE" ] && return 0
  [ -f "$ENV_EXAMPLE" ] || { echo "missing $ENV_EXAMPLE" >&2; exit 1; }
  command -v openssl >/dev/null 2>&1 || { echo "openssl is required to generate secrets" >&2; exit 1; }
  local jwt pg tmp
  jwt="$(openssl rand -hex 32)"
  pg="$(openssl rand -hex 32)"
  mkdir -p "$(dirname "$ENV_FILE")"
  tmp="$(umask 077 && mktemp "$ENV_FILE.XXXXXX")"
  sed -e "s|^JWT_SECRET=.*|JWT_SECRET=$jwt|" \
      -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$pg|" "$ENV_EXAMPLE" >"$tmp"
  chmod 600 "$tmp"
  # ln fails if the target appeared meanwhile, so an existing file is never replaced.
  if ln "$tmp" "$ENV_FILE" 2>/dev/null; then
    echo "Created $ENV_FILE (mode 600) with generated secrets."
  fi
  rm -f "$tmp"
}

# Last value of KEY in the env file (empty if absent or file missing).
env_value() {
  [ -f "$ENV_FILE" ] || return 0
  sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1 | tr -d '\r"'"'"
}

tunnel_enabled() {
  [ "$(env_value BOUNTYHUB_TUNNEL)" = on ]
}

tunnel_service() {
  if [ -n "$(env_value TUNNEL_TOKEN)" ]; then echo tunnel-named; else echo tunnel; fi
}

tunnel_profile() {
  if [ -n "$(env_value TUNNEL_TOKEN)" ]; then echo tunnel-named; else echo tunnel-quick; fi
}

# Set only the BOUNTYHUB_TUNNEL line of the env file, keeping its inode and mode.
set_tunnel_mode() {
  local value="$1" tmp
  tmp="$(umask 077 && mktemp "${TMPDIR:-/tmp}/bountyhub-env.XXXXXX")"
  if grep -q '^BOUNTYHUB_TUNNEL=' "$ENV_FILE"; then
    sed "s|^BOUNTYHUB_TUNNEL=.*|BOUNTYHUB_TUNNEL=$value|" "$ENV_FILE" >"$tmp"
  else
    { cat "$ENV_FILE"; printf 'BOUNTYHUB_TUNNEL=%s\n' "$value"; } >"$tmp"
  fi
  cat "$tmp" >"$ENV_FILE"
  rm -f "$tmp"
}

compose() {
  local -a args=(-p "$PROJECT" -f "$COMPOSE_FILE" --env-file "$ENV_FILE")
  if tunnel_enabled; then
    args+=(--profile "$(tunnel_profile)")
    export AUTH_COOKIE_SECURE=true FRONTEND_BIND=127.0.0.1
  fi
  if docker compose version >/dev/null 2>&1; then
    docker compose "${args[@]}" "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "${args[@]}" "$@"
  else
    echo "neither 'docker compose' nor 'docker-compose' is available" >&2
    exit 1
  fi
}

prepare() {
  setup_runtime
  ensure_env_file
}

# Newest quick-tunnel URL in the tunnel container's log, waiting up to $1 seconds.
quick_tunnel_url() {
  local wait="$1" i=0 found
  while :; do
    found="$(compose logs --no-color tunnel 2>/dev/null \
      | grep -o 'https://[A-Za-z0-9-]*\.trycloudflare\.com' | tail -n 1 || true)"
    if [ -n "$found" ]; then echo "$found"; return 0; fi
    [ "$i" -lt "$wait" ] || return 1
    sleep 1
    i=$((i + 1))
  done
}

# Print the public URL; $1 is the max seconds to wait for a quick tunnel.
public_url() {
  local host
  if [ -n "$(env_value TUNNEL_TOKEN)" ]; then
    host="$(env_value PUBLIC_HOSTNAME)"
    if [ -z "$host" ]; then
      echo "PUBLIC_HOSTNAME is empty in $ENV_FILE" >&2
      return 1
    fi
    echo "https://$host"
  else
    quick_tunnel_url "$1" || { echo "no trycloudflare.com URL in the tunnel log yet" >&2; return 1; }
  fi
}

registration_closed() {
  curl -fsS -m 5 "http://127.0.0.1:8000/auth/status" 2>/dev/null \
    | grep -Eq '"registration_open"[[:space:]]*:[[:space:]]*false'
}

tunnel_cmd() {
  local sub="${1:-}"
  [ $# -eq 1 ] || usage
  prepare
  case "$sub" in
    up)
      if ! registration_closed; then
        echo "refusing: backend at 127.0.0.1:8000 did not answer registration_open=false." >&2
        echo "Start the stack and register your account first (scripts/stack.sh up)." >&2
        exit 1
      fi
      set_tunnel_mode on
      compose up -d --build
      public_url 30 || echo "run '$(basename "$0") tunnel url' again in a moment" >&2
      ;;
    down)
      set_tunnel_mode off
      compose --profile tunnel-quick --profile tunnel-named rm -sf tunnel tunnel-named
      compose up -d --no-deps frontend
      echo "Tunnel off; frontend is back on the LAN address."
      ;;
    url)
      tunnel_enabled || { echo "tunnel is off" >&2; exit 1; }
      public_url 30
      ;;
    status)
      if tunnel_enabled; then
        echo "tunnel: on ($(tunnel_profile))"
        compose ps "$(tunnel_service)" frontend
      else
        echo "tunnel: off"
      fi
      ;;
    *) usage ;;
  esac
}

print_urls() {
  local ip
  echo "http://localhost:$PORT"
  if tunnel_enabled; then
    public_url 0 || true
    return 0
  fi
  for ip in $(hostname -I 2>/dev/null || true); do
    case "$ip" in
      *:*) echo "http://[$ip]:$PORT" ;;
      *) echo "http://$ip:$PORT" ;;
    esac
  done
}

[ $# -ge 1 ] || usage
cmd="$1"
shift

case "$cmd" in
  up)
    [ $# -eq 0 ] || usage
    prepare
    compose up -d --build
    ;;
  down)
    [ $# -eq 0 ] || usage
    prepare
    compose --profile tunnel-quick --profile tunnel-named down
    ;;
  restart)
    [ $# -eq 0 ] || usage
    prepare
    compose restart
    ;;
  ps)
    [ $# -eq 0 ] || usage
    prepare
    compose ps
    ;;
  logs)
    [ $# -le 1 ] || usage
    prepare
    compose logs -f --tail=100 "$@"
    ;;
  config)
    [ $# -eq 0 ] || usage
    prepare
    compose config
    ;;
  tunnel)
    tunnel_cmd "$@"
    ;;
  urls)
    [ $# -eq 0 ] || usage
    if tunnel_enabled; then setup_runtime; fi
    print_urls
    ;;
  reset)
    if [ "${1:-}" != "--yes" ] || [ $# -ne 1 ]; then
      echo "reset DESTROYS the database (removes the bountyhub volumes) and starts a fresh stack." >&2
      echo "Re-run as: $(basename "$0") reset --yes" >&2
      exit 2
    fi
    prepare
    compose --profile tunnel-quick --profile tunnel-named down -v
    compose up -d --build
    ;;
  *)
    usage
    ;;
esac
