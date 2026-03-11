#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

APP_DIR="${APP_DIR:-/opt/dealgoblin}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${APP_DIR}/.env"
DATA_DIR="${APP_DIR}/data"
CONTAINER_UID="${CONTAINER_UID:-1000}"
CONTAINER_GID="${CONTAINER_GID:-1000}"
SERVICE_NAME="dealgoblin.service"
SERVICE_SOURCE="${REPO_ROOT}/deploy/systemd/${SERVICE_NAME}"
SERVICE_TARGET="/etc/systemd/system/${SERVICE_NAME}"

REQUIRED_ENV_VARS=(
  "TELEGRAM_API_ID"
  "TELEGRAM_API_HASH"
  "BOT_TOKEN"
  "OWNER_CHAT_ID"
  "SOURCE_CHAT_IDS"
)

env_ready=false

log() {
  printf '[bootstrap] %s\n' "$*"
}

warn() {
  printf '[bootstrap] WARNING: %s\n' "$*" >&2
}

die() {
  printf '[bootstrap] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "Required command not found: ${cmd}"
}

validate_host() {
  [[ -r /etc/os-release ]] || die "Cannot determine OS: /etc/os-release is missing."
  # shellcheck disable=SC1091
  . /etc/os-release
  [[ "${ID:-}" == "ubuntu" ]] || die "Unsupported OS '${ID:-unknown}'. This script supports Ubuntu only."
}

install_docker_if_missing() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker Engine and Compose plugin are already installed."
    return
  fi

  require_command sudo
  require_command dpkg

  log "Installing Docker Engine and Compose plugin..."
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings

  if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  fi
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  # shellcheck disable=SC1091
  . /etc/os-release
  local arch
  arch="$(dpkg --print-architecture)"
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo systemctl enable --now docker
  log "Docker installation complete."
}

ensure_app_layout() {
  require_command sudo

  log "Ensuring app directory exists at ${APP_DIR}..."
  sudo mkdir -p "${APP_DIR}"
  sudo chown "${USER}:${USER}" "${APP_DIR}"

  sudo mkdir -p "${DATA_DIR}"
  sudo chown -R "${CONTAINER_UID}:${CONTAINER_GID}" "${DATA_DIR}"
  sudo chmod 700 "${DATA_DIR}"
}

inspect_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    warn "Missing ${ENV_FILE}. Create it from .env.example before starting the service."
    return
  fi

  local missing=()
  local empty=()
  local key
  local value

  for key in "${REQUIRED_ENV_VARS[@]}"; do
    if ! grep -qE "^${key}=" "${ENV_FILE}"; then
      missing+=("${key}")
      continue
    fi

    value="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 | cut -d '=' -f 2-)"
    value="${value//[[:space:]]/}"
    if [[ -z "${value}" ]]; then
      empty+=("${key}")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    warn "Missing required keys in ${ENV_FILE}: ${missing[*]}"
  fi
  if (( ${#empty[@]} > 0 )); then
    warn "Empty required values in ${ENV_FILE}: ${empty[*]}"
  fi

  if (( ${#missing[@]} == 0 )) && (( ${#empty[@]} == 0 )); then
    env_ready=true
    log "${ENV_FILE} contains all required keys."
  fi
}

install_systemd_service() {
  require_command sudo
  require_command systemctl

  [[ -f "${SERVICE_SOURCE}" ]] || die "Service template not found: ${SERVICE_SOURCE}"

  if [[ "${REPO_ROOT}" != "${APP_DIR}" ]]; then
    warn "Repository path is ${REPO_ROOT}, but systemd service expects ${APP_DIR}."
    warn "Ensure code is deployed at ${APP_DIR} before starting service."
  fi

  log "Installing systemd unit ${SERVICE_NAME}..."
  sudo cp "${SERVICE_SOURCE}" "${SERVICE_TARGET}"
  sudo systemctl daemon-reload
  sudo systemctl enable "${SERVICE_NAME}"

  if [[ "${env_ready}" == "true" ]]; then
    log "Starting ${SERVICE_NAME}..."
    sudo systemctl restart "${SERVICE_NAME}"
    sudo systemctl --no-pager --full status "${SERVICE_NAME}"
  else
    warn "Skipping service start until required .env values are configured."
  fi
}

print_next_steps() {
  if [[ ! -f "${DATA_DIR}/telethon.session" ]]; then
    cat <<EOF
[bootstrap] No Telethon session file detected.
[bootstrap] Complete first-time authorization with:
  cd ${APP_DIR}
  docker compose run --rm dealgoblin
[bootstrap] Then start the long-running service:
  cd ${APP_DIR}
  docker compose up -d
EOF
  fi

  log "Bootstrap complete."
}

main() {
  validate_host
  require_command apt-get
  ensure_app_layout
  install_docker_if_missing
  inspect_env_file
  install_systemd_service
  print_next_steps
}

main "$@"
