# Configuration — Environment Variables

All configuration is done via environment variables. Copy `.env.example` to `.env` and fill in your values.

---

## Required Variables

| Variable | Example | Description |
|----------|---------|-------------|
| `DATABASE_NAME` | `hackathon_db` | PostgreSQL database name |
| `DATABASE_HOST` | `localhost` | PostgreSQL host (use `pgbouncer` in Docker) |
| `DATABASE_PORT` | `5432` | PostgreSQL port |
| `DATABASE_USER` | `postgres` | PostgreSQL username |
| `DATABASE_PASSWORD` | `postgres` | PostgreSQL password — **change in production** |

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_DEBUG` | `false` | Enable Flask debug mode — **never true in production** |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL for caching |
| `CACHE_TYPE` | `RedisCache` | Flask-Caching backend (`RedisCache` or `SimpleCache`) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Docker Compose Overrides

When running via Docker Compose, the app containers override some variables automatically:

```yaml
environment:
  DATABASE_HOST: pgbouncer   # routes through connection pooler
  DATABASE_PORT: "5432"
  REDIS_URL: redis://redis:6379/0
```

These are set in `docker-compose.yml` and take precedence over `.env`.

---

## Example .env File

```bash
FLASK_DEBUG=false
DATABASE_NAME=hackathon_db
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=your_secure_password_here
REDIS_URL=redis://localhost:6379/0
```

---

## Secrets in Production

- Never commit `.env` to git (it's in `.gitignore`)
- Rotate `DATABASE_PASSWORD` before going live
- Use Docker secrets or a secrets manager (Vault, AWS SSM) for production deployments
