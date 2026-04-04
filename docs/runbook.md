# Runbook — URL Shortener

## Alert: ServiceDown

**Trigger:** A URL Shortener app instance has been unreachable for >1 minute.

**Steps:**
1. Check container status: `docker compose ps`
2. If a container is exited: `docker compose up -d` — Docker's `restart: always` should have already restarted it.
3. Check logs: `docker compose logs app1 --tail=50` or `docker compose logs app2 --tail=50`
4. If OOM killed (`Exited (137)`): reduce `--workers` in the Dockerfile CMD or add memory limits.
5. Verify recovery: `curl http://localhost/health` → `{"status": "ok"}`

---

## Alert: HighErrorRate

**Trigger:** HTTP 5xx rate > 5% over 2 minutes.

**Steps:**
1. Check recent logs for exceptions: `docker compose logs app1 app2 --tail=100 | grep ERROR`
2. Check database connectivity: `docker compose exec db pg_isready -U postgres`
3. Check Redis connectivity: `docker compose exec redis redis-cli ping` → should return `PONG`
4. If DB is down: `docker compose up -d db` and wait for health check to pass.
5. If Redis is down: `docker compose up -d redis` — app falls back to PostgreSQL automatically.

---

## Alert: HighLatency

**Trigger:** p95 latency > 3s for >3 minutes.

**Steps:**
1. Check Redis cache hit rate — if Redis is down, every redirect hits PostgreSQL.
2. `docker compose exec redis redis-cli info stats | grep keyspace_hits`
3. Check DB slow queries: `docker compose exec db psql -U postgres hackathon_db -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"`
4. Scale up: add a 3rd app instance by duplicating `app1` in `docker-compose.yml` and restarting.
5. If under active load test: confirm load is expected, monitor until test completes.

---

## DB Connection Lost

**Symptoms:** Logs show `OperationalError: could not connect to server`, all requests return 500.

**Steps:**
1. `docker compose ps db` — check if the PostgreSQL container is running.
2. If stopped: `docker compose up -d db`
3. Wait ~10 seconds for healthcheck, then app connections auto-recover (Peewee reconnects on each request).
4. Verify: `curl http://localhost/health` → `{"status": "ok"}`

---

## Manual Log Access (no SSH)

**Via Docker CLI:**
```bash
docker compose logs --follow
docker compose logs app1 --since=5m
```

**Live JSON stream:**
```bash
docker compose logs --follow --no-log-prefix app1 | python3 -m json.tool
```
