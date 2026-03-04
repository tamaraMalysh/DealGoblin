#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

APP_DIR="${APP_DIR:-/opt/dealgoblin}"
DEPLOY_REF="${1:-${DEPLOY_REF:-main}}"
LOCK_FILE="${LOCK_FILE:-/tmp/dealgoblin-deploy.lock}"
LOG_TAIL_LINES="${LOG_TAIL_LINES:-120}"

log() {
  printf '[deploy] %s\n' "$*"
}

die() {
  printf '[deploy] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "Required command not found: ${cmd}"
}

main() {
  require_command flock
  require_command git
  require_command docker

  [[ -d "${APP_DIR}/.git" ]] || die "Not a git repository: ${APP_DIR}"

  exec 9>"${LOCK_FILE}"
  if ! flock -n 9; then
    die "Another deployment is already in progress. Lock file: ${LOCK_FILE}"
  fi

  cd "${APP_DIR}"
  [[ -f .env ]] || die "Missing ${APP_DIR}/.env. Create it from .env.example before deploying."

  log "Fetching latest '${DEPLOY_REF}' from origin..."
  git fetch --prune origin "${DEPLOY_REF}"

  if git show-ref --verify --quiet "refs/heads/${DEPLOY_REF}"; then
    git checkout "${DEPLOY_REF}"
  else
    git checkout -B "${DEPLOY_REF}" "origin/${DEPLOY_REF}"
  fi

  git pull --ff-only origin "${DEPLOY_REF}"

  log "Building image and updating running service..."
  docker compose up -d --build dealgoblin

  log "Container status:"
  docker compose ps

  log "Recent logs:"
  docker compose logs --tail="${LOG_TAIL_LINES}" dealgoblin

  log "Deployment completed."
}

main "$@"
