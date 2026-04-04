# PE Hackathon — URL Shortener

Production Engineering Hackathon 2026 · Built by Team [Your Team Name]

A production-ready URL shortener with automated testing, CI/CD, structured observability, and chaos-resilient deployment.

---

## Architecture

```
User
 │
 ▼
FastAPI App  ──► PostgreSQL (peewee ORM)
 │
 ├── /metrics  ──► Prometheus ──► Alertmanager ──► Discord
 │
 └── Grafana (reads Prometheus)
```

All services run in Docker. The app uses `restart: always` so it self-heals after crashes.

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Service + DB health check |
| GET | `/metrics` | Prometheus metrics |
| POST | `/urls` | Shorten a URL |
| GET | `/urls` | List active URLs |
| GET | `/urls/{code}` | Get URL by short code |
| DELETE | `/urls/{code}` | Deactivate a URL |
| GET | `/r/{code}` | Redirect to original URL |
| POST | `/users` | Create a user |
| GET | `/users/{id}` | Get user + their URLs |

Full interactive docs: `http://localhost:8000/docs`

---

## Quickstart (local, no Docker)

**Requirements:** Python 3.11+, PostgreSQL running on `localhost:5432`

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd pe-hackathon

# 2. Copy env and install
cp .env.example .env
pip install -e ".[dev]"

# 3. Start the app
python run.py
```

App is live at `http://localhost:8000`

---

## Quickstart (full Docker stack)

```bash
docker-compose up --build
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / admin) |
| Alertmanager | http://localhost:9093 |

---

## Running tests

```bash
# All tests + coverage report
pytest

# Verbose output
pytest -v

# Coverage only
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

Tests use an in-memory SQLite database — no Postgres required.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `127.0.0.1` | Postgres host |
| `DB_PORT` | `5432` | Postgres port |
| `DB_NAME` | `postgres` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `1234` | Database password |

---

## Chaos engineering demo

```bash
# 1. Start the stack
docker-compose up -d

# 2. Kill the app container
docker kill pe-hackathon-app-1

# 3. Watch it restart automatically
watch docker ps

# 4. Confirm it recovered
curl http://localhost:8000/health
```

---

## Sending bad input (graceful error demo)

```bash
# Missing http:// scheme — returns 422
curl -X POST http://localhost:8000/urls \
  -H "Content-Type: application/json" \
  -d '{"original_url": "google.com"}'

# Missing body field — returns 422
curl -X POST http://localhost:8000/urls \
  -H "Content-Type: application/json" \
  -d '{}'

# Non-existent short code — returns 404
curl http://localhost:8000/urls/xxxxxx
```

---

## Docs

- [Failure Modes](docs/failure-modes.md)
- [Runbook](docs/runbook.md)
- [Decision Log](docs/decision-log.md)

---

## CI/CD

GitHub Actions runs on every push. The pipeline:
1. Installs dependencies
2. Runs the full test suite
3. Enforces 70%+ code coverage
4. **Blocks merge if any test fails**

See `.github/workflows/ci.yml`.

---

## Discord alerts setup

1. Create a webhook in your Discord server: `Server Settings → Integrations → Webhooks`
2. Copy the webhook URL
3. Replace `YOUR_DISCORD_WEBHOOK_URL` in `monitoring/alertmanager.yml`
4. Restart the stack: `docker-compose restart alertmanager`

Alerts fire for: service down, high error rate (> 5%), high latency (p95 > 1s).
