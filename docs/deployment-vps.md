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

## 3) Prepare persistent data directory

```bash
mkdir -p data
chmod 700 data
```

If migrating an existing bot, copy your current `telethon.session` into `data/` before first start.

## 4) Build and start

```bash
docker compose up -d --build
```

For first Telethon user authorization (if no existing session):

```bash
docker compose run --rm dealgoblin
```

After login completes, stop that one-off container and start the service in background:

```bash
docker compose up -d
```

## 5) Verify runtime and persistence

```bash
docker compose ps
docker compose logs -f --tail=200
ls -lah data/
```

Healthy logs should show the bot polling loop, Telethon connection, and notifier loop starting.

## Optional boot-start with systemd

Install the unit file from `deploy/systemd/dealgoblin.service`:

```bash
sudo cp deploy/systemd/dealgoblin.service /etc/systemd/system/dealgoblin.service
sudo systemctl daemon-reload
sudo systemctl enable --now dealgoblin.service
sudo systemctl status dealgoblin.service
```

## Operations

- Restart service: `docker compose restart`
- Update app: `git pull && docker compose up -d --build`
- Follow logs: `docker compose logs -f --tail=200`

## SQLite Decision and Migration Trigger

SQLite is the default for now because:

- It already powers FTS5 search in this codebase.
- Single-instance VPS deployment keeps SQLite durable and simple.

Revisit a move to managed Postgres when either condition is true:

- You need multiple bot replicas (HA/horizontal scale).
- Write pressure makes SQLite single-writer behavior a bottleneck.

Current backup stance for this deployment profile: no off-server backups yet.
