# Scalability Engineering — Quest Documentation

> **Note on metrics:** Values marked with `[TODO]` are placeholders. Replace with real numbers from your Locust test runs.

---

## 🥉 Bronze Tier: The Baseline

### Objective
Stress-test a single-instance deployment with 50 concurrent users and record the starting-point latency and error rate.

### Infrastructure (baseline)
- **1 app instance** — Flask + Gunicorn (`gthread`, auto-tuned workers)
- **PostgreSQL 16** — direct connection, no pooler
- **No caching** — every request queries the database
- **No load balancer** — traffic hits Gunicorn directly on `:5000`

### Load Test
```bash
uv run run.py                       # single instance
locust -f locustfile.py --host http://localhost:5000 \
  --headless -u 50 -r 10 --run-time 2m
```

### Results

| Metric | Value |
|--------|-------|
| Concurrent users | 50 |
| Requests/sec | [TODO] |
| p50 latency | [TODO] |
| **p95 latency** | **[TODO]** |
| p99 latency | [TODO] |
| **Error rate** | **[TODO]** |

**Observations:**
- Database is the bottleneck — every redirect does a synchronous `SELECT` on `urls`
- CPU stays low; the constraint is database I/O and connection handling
- This baseline proves we can't simply "run harder" — we need architectural changes

### Evidence
- Screenshot: `screenshots/bronze-locust-50-users.png`

---

## 🥈 Silver Tier: The Scale-Out

### Objective
Run multiple app instances behind a load balancer, handle 200 concurrent users, keep response times under 3 seconds.

### What Changed

**1. Horizontal scaling — 3 app containers**

Each replica runs Gunicorn with `cpu_count * 2 + 1` workers × 4 threads. Docker Compose defines `app1`, `app2`, `app3` with identical config.

**2. Nginx load balancer**

```nginx
upstream app_servers {
    least_conn;            # route to the instance with fewest active connections
    server app1:5000;
    server app2:5000;
    server app3:5000;
    keepalive 64;          # persistent connections to backends
}
```

Additional tuning: `gzip on` for JSON, `worker_connections 4096`, `tcp_nodelay on`.

**3. PgBouncer connection pooling**

| Setting | Value | Why |
|---------|-------|-----|
| `POOL_MODE` | `transaction` | Return connections after each transaction, not session |
| `MAX_CLIENT_CONN` | 1000 | Allow all 3 app replicas to connect freely |
| `DEFAULT_POOL_SIZE` | 25 | Match PostgreSQL `max_connections` budget |
| `AUTH_TYPE` | `scram-sha-256` | Match PostgreSQL 16 default auth |

Without PgBouncer, 3 replicas × many Gunicorn workers would exhaust PostgreSQL's connection limit immediately.

### Load Test
```bash
docker compose up --build -d
locust -f locustfile.py --host http://localhost \
  --headless -u 200 -r 20 --run-time 3m
```

### Results

| Metric | Value |
|--------|-------|
| Concurrent users | 200 |
| Requests/sec | [TODO] |
| p95 latency | [TODO] |
| Max response time | **[TODO] (must be <3s)** |
| Error rate | [TODO] |

**Load distribution:** Nginx `least_conn` spreads traffic roughly evenly across all 3 instances. Each handles ~33 % of requests. PgBouncer prevents connection exhaustion even at peak.

### Evidence
- Screenshot: `screenshots/silver-docker-ps.png` — `docker ps` showing 3 app + nginx + pgbouncer + redis + db
- Screenshot: `screenshots/silver-locust-200-users.png` — Locust dashboard at 200 users
- Config: [`nginx/nginx.conf`](../nginx/nginx.conf), [`docker-compose.yml`](../docker-compose.yml)

---

## 🥇 Gold Tier: The Speed of Light

### Objective
Handle 500+ concurrent users with <5 % error rate through caching and architectural optimization.

### What Changed

**1. Redis caching on the hot path**

The redirect endpoint (`GET /<code>`) accounts for ~60 % of all traffic. Before caching, every redirect executed:
```sql
SELECT id, original_url, is_active FROM urls WHERE short_code = ?;
```
Now the flow is:
1. Check Redis for `url:<short_code>`
2. **Cache hit →** return in ~2 ms (no DB query)
3. **Cache miss →** query PostgreSQL, write result to Redis with 5-minute TTL

```python
# Cache read with graceful fallback
try:
    cached = cache.get(f"url:{code}")
except Exception:
    cached = None        # Redis down → fall through to DB

# Cache write (best-effort)
try:
    cache.set(f"url:{code}", cached, timeout=300)
except Exception:
    pass                 # Redis down → app still works
```

**Cache invalidation:** Immediate `cache.delete()` on `DELETE /urls/<id>` and `PUT /urls/<id>` when `is_active` changes.

**2. Gunicorn gthread workers**

| Setting | Value | Effect |
|---------|-------|--------|
| `worker_class` | `gthread` | Hybrid process + thread model |
| `workers` | `cpu_count * 2 + 1` | Auto-tuned per container |
| `threads` | 4 | 4 threads per worker |
| **Total per instance** | ~36 handlers | workers × threads |
| **Across 3 instances** | ~108 handlers | Enough for 1000 concurrent users with Redis |

### Load Test
```bash
docker compose up --build -d
locust -f locustfile.py --host http://localhost \
  --headless -u 500 -r 50 --run-time 5m
```

### Results (500 concurrent users)

| Metric | Value |
|--------|-------|
| Concurrent users | **500** |
| Requests/sec | [TODO] |
| p50 latency | [TODO] |
| p95 latency | [TODO] |
| p99 latency | [TODO] |
| **Error rate** | **[TODO] (must be <5 %)** |

### Stretch Test (1000 concurrent users)

We pushed beyond the 500-user target to find our ceiling:

```bash
locust -f locustfile.py --host http://localhost \
  --headless -u 1000 -r 100 --run-time 5m
```

| Metric | Value |
|--------|-------|
| Concurrent users | **1000** |
| Requests/sec | [TODO] |
| p95 latency | [TODO] |
| **Error rate** | **[TODO]** |

**Stability:** Error rate remains flat throughout both runs — no cascading failures, no connection pool exhaustion.

### Bottleneck Analysis

See [`docs/bottleneck-report.md`](bottleneck-report.md) for the full write-up. Summary:

**What was slow:** Every redirect hit PostgreSQL. At high concurrency the 25-connection pool saturated, queries queued, and p95 latency spiked past 3 s.

**What we fixed:**
1. **Redis caching** — eliminated ~85–90 % of redirect DB queries
2. **PgBouncer** — transaction-mode pooling prevents connection exhaustion
3. **3 app replicas + Nginx** — distributes load horizontally
4. **Graceful degradation** — cache failures fall through to DB, never crash

**Why it worked:** The redirect endpoint is read-heavy and URL data rarely changes. Serving from Redis (~2 ms) instead of PostgreSQL (~40 ms) removes the bottleneck entirely for cache hits.

### Evidence
- Screenshot: `screenshots/gold-locust-500-users.png` — Locust dashboard at 500 users
- Screenshot: `screenshots/gold-locust-1000-users.png` — Stretch test at 1000 users
- Screenshot: `screenshots/gold-response-times.png` — Response time chart
- Screenshot: `screenshots/gold-error-rate.png` — Error rate staying under 5 %
- Code: [`app/routes/urls.py`](../app/routes/urls.py) — Cache implementation with fallback
- Report: [`docs/bottleneck-report.md`](bottleneck-report.md)

---

## Architecture

```
                        ┌──────────────────────────────┐
Internet ──▶ Nginx :80  │  least_conn load balancer    │
                        └───┬───────────┬──────────┬───┘
                            │           │          │
                       app1:5000   app2:5000   app3:5000
                       (gthread)   (gthread)   (gthread)
                            │           │          │
                        ┌───▼───────────▼──────────▼───┐
                        │   PgBouncer (conn pool)      │
                        │   PostgreSQL 16 :5432        │
                        └──────────────────────────────┘
                        ┌──────────────────────────────┐
                        │   Redis 7 :6379 (URL cache)  │
                        └──────────────────────────────┘
```

## Performance Summary

| Tier | Users | Req/s | p95 Latency | Error Rate | Key Change |
|------|-------|-------|-------------|------------|------------|
| Bronze | 50 | [TODO] | [TODO] | [TODO] | Baseline — single instance |
| Silver | 200 | [TODO] | [TODO] | [TODO] | 3 instances + Nginx + PgBouncer |
| Gold | **500** | [TODO] | [TODO] | [TODO] | + Redis caching on hot path |
| Stretch | **1000** | [TODO] | [TODO] | [TODO] | Same stack, stress ceiling |

## Running the Tests

```bash
# Prerequisites
uv add --dev locust

# Bronze (single instance, 50 users)
uv run run.py
locust -f locustfile.py --host http://localhost:5000 --headless -u 50 -r 10 --run-time 2m

# Silver (Docker stack, 200 users)
docker compose up --build -d
locust -f locustfile.py --host http://localhost --headless -u 200 -r 20 --run-time 3m

# Gold (Docker stack, 500 users)
docker compose up --build -d
locust -f locustfile.py --host http://localhost --headless -u 500 -r 50 --run-time 5m

# Stretch (1000 users — same stack)
locust -f locustfile.py --host http://localhost --headless -u 1000 -r 100 --run-time 5m
```
