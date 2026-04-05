# Deploy Guide

## Prerequisites

- Docker Desktop installed and running
- Git
- A `.env` file configured (see [config.md](config.md))

---

## First-Time Deploy

```bash
# 1. Clone the repo
git clone https://github.com/payne19/PE-Hackathon-Template-2026.git
cd PE-Hackathon-Template-2026

# 2. Configure environment
cp .env.example .env
# Edit .env and set DATABASE_PASSWORD and any other secrets

# 3. Build and start all services
docker compose up --build -d

# 4. Verify everything is healthy
docker compose ps
curl http://localhost/health
# → {"status": "ok"}

# 5. Seed the database (first time only)
docker compose exec app1 uv run load_data.py
```

---

## Updating the App (New Code Deploy)

```bash
# 1. Pull latest code
git pull origin main

# 2. Rebuild app images only (zero downtime — other services stay up)
docker compose build app1 app2 app3

# 3. Restart app instances one at a time (rolling)
docker compose up -d --no-deps app1
docker compose up -d --no-deps app2
docker compose up -d --no-deps app3

# 4. Verify
curl http://localhost/health
```

---

## Rollback

If a new deploy breaks something:

```bash
# Option 1: Roll back to previous Git commit
git log --oneline -5          # find the last good commit hash
git checkout <commit-hash>
docker compose build app1 app2 app3
docker compose up -d --no-deps app1 app2 app3

# Option 2: Roll back using Docker image tags
# (if you tagged images before deploying)
docker tag pe-hackathon-template-2026-app1:latest pe-hackathon-template-2026-app1:backup
# restore with:
docker tag pe-hackathon-template-2026-app1:backup pe-hackathon-template-2026-app1:latest
docker compose up -d --no-deps app1 app2 app3
```

---

## Database Migrations

Peewee does not have a built-in migration tool. Schema changes are applied manually:

```bash
# Connect to the database
docker compose exec db psql -U postgres hackathon_db

# Run your ALTER TABLE or CREATE TABLE statements
ALTER TABLE url ADD COLUMN click_count INTEGER DEFAULT 0;
\q
```

For destructive changes (DROP COLUMN, etc.) always take a backup first:
```bash
docker compose exec db pg_dump -U postgres hackathon_db > backup_$(date +%Y%m%d).sql
```

---

## Stopping the Stack

```bash
# Stop all containers (keeps data)
docker compose down

# Stop and delete all data volumes (full reset)
docker compose down -v
```

---

## Monitoring After Deploy

- Health: `curl http://localhost/health`
- Logs: `docker compose logs app1 app2 --follow`
- Metrics: `http://localhost/metrics`
- Grafana: `http://localhost:3000` (admin/admin)
- Alertmanager: `http://localhost:9093`
