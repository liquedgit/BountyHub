#!/usr/bin/env bash
# Drive the BountyHub compose stack (project "bountyhub") by hand.
# Usage: scripts/stack.sh {up|down|restart|ps|logs [service]|config|urls|reset --yes}
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

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose -p "$PROJECT" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose -p "$PROJECT" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
  else
    echo "neither 'docker compose' nor 'docker-compose' is available" >&2
    exit 1
  fi
}

prepare() {
  setup_runtime
  ensure_env_file
}

print_urls() {
  local ip
  echo "http://localhost:$PORT"
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
    compose down
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
  urls)
    [ $# -eq 0 ] || usage
    print_urls
    ;;
  reset)
    if [ "${1:-}" != "--yes" ] || [ $# -ne 1 ]; then
      echo "reset DESTROYS the database (removes the bountyhub volumes) and starts a fresh stack." >&2
      echo "Re-run as: $(basename "$0") reset --yes" >&2
      exit 2
    fi
    prepare
    compose down -v
    compose up -d --build
    ;;
  *)
    usage
    ;;
esac
