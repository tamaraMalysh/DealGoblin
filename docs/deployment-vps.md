# VPS Deployment (Docker Compose + SQLite)

This project is designed to run as a single long-lived process with persistent local state:

- `data/dealgoblin.sqlite3` (+ `-wal` and `-shm`)
- `data/telethon.session`

Use a single always-on VPS with local SSD storage and run one container replica.

## Recommended Host

- Ubuntu `24.04` LTS
- `1 vCPU / 2 GB RAM` minimum
- SSH key auth only
- Firewall: open `22/tcp` only (bot uses polling, no inbound webhook port)

## 1) Provision server and clone repo

```bash
sudo mkdir -p /opt/dealgoblin
sudo chown "$USER":"$USER" /opt/dealgoblin
cd /opt/dealgoblin
git clone <your-repo-url> .
```

## 2) Configure secrets and source list

```bash
cp .env.example .env
```

Edit `.env` and set:

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `BOT_TOKEN`
- `OWNER_CHAT_ID`
- `SOURCE_CHAT_IDS`
- `RUNTIME_LOCK_PATH` (optional; default `data/runtime.lock`)

## 3) Run one-time host bootstrap script

The bootstrap script validates Ubuntu, installs Docker + Compose if missing, prepares `/opt/dealgoblin/data`, installs and enables `dealgoblin.service`, and checks `.env` completeness.

```bash
chmod +x deploy/scripts/bootstrap_server.sh deploy/scripts/deploy_server.sh
./deploy/scripts/bootstrap_server.sh
```

If you copied `data/` files onto the server as `root`, ensure the bind-mounted directory remains writable by the container user:

```bash
sudo chown -R 1000:1000 /opt/dealgoblin/data
```

## 4) First Telethon authorization (only when `data/telethon.session` is absent)

```bash
docker compose run --rm dealgoblin
```

Do not run `docker compose run --rm dealgoblin` while `docker compose up -d` is already running.
Polling bots must have only one active runtime per token.

## 5) Deploy current revision

```bash
./deploy/scripts/deploy_server.sh main
```

The deploy script uses `flock` to prevent concurrent deploy runs, performs `git fetch` + `git pull --ff-only`, rebuilds/restarts the service container, then prints `docker compose ps` and recent logs.

## 6) Verify runtime and persistence

```bash
docker compose ps
docker compose logs -f --tail=200 dealgoblin
ls -lah data/
sudo systemctl status dealgoblin.service
```

Healthy logs should show the bot polling loop, Telethon connection, and notifier loop starting.

## 7) Configure GitHub manual deploy (`workflow_dispatch`)

This repository includes `.github/workflows/deploy.yml`, which SSHes into the VPS and runs:

```bash
cd /opt/dealgoblin && ./deploy/scripts/deploy_server.sh <ref>
```

Set these repository secrets:

- `DO_SSH_HOST`
- `DO_SSH_PORT` (optional, defaults to `22`)
- `DO_SSH_USER`
- `DO_SSH_PRIVATE_KEY`
- `DO_SSH_KNOWN_HOSTS`

Generate known hosts value from your workstation:

```bash
ssh-keyscan -H <droplet-host-or-ip>
```

After secrets are set:

1. Open GitHub Actions.
2. Select workflow `Deploy`.
3. Click `Run workflow`.
4. Keep default `ref=main` unless intentionally deploying another branch.

## Operations

- Deploy on server: `./deploy/scripts/deploy_server.sh main`
- Deploy from GitHub UI: run workflow `Deploy` with `ref=main`
- Restart service: `docker compose restart dealgoblin`
- Follow logs: `docker compose logs -f --tail=200 dealgoblin`

## Conflict Recovery Runbook

If logs show `TelegramConflictError: terminated by other getUpdates request`:

1. Find and stop duplicate runtimes (extra local process, extra container, or second host).
2. Keep exactly one DealGoblin runtime active for the bot token.
3. Restart the surviving service once: `docker compose restart dealgoblin`.
4. Verify recovery by tailing logs for at least 10 minutes and ensuring conflict lines do not recur.

## SQLite Decision and Migration Trigger

SQLite is the default for now because:

- It already powers FTS5 search in this codebase.
- Single-instance VPS deployment keeps SQLite durable and simple.

Revisit a move to managed Postgres when either condition is true:

- You need multiple bot replicas (HA/horizontal scale).
- Write pressure makes SQLite single-writer behavior a bottleneck.

Current backup stance for this deployment profile: no off-server backups yet.
