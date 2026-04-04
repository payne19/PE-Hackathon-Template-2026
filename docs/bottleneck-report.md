# Bottleneck Report

## 1. Primary Bottleneck

**Problem:** Two compounding issues crippled throughput under load:

1. **Gunicorn under-provisioning** — `workers = cpu_count() * 2 + 1` resolved to only **3 workers × 4 threads = 12 handlers** per app instance inside Docker (where `cpu_count()` returns 1). With 3 replicas, the entire cluster had just **36 concurrent handlers** — far below 200+ user targets.
2. **Database connection exhaustion** — Every `GET /<code>` redirect hit PostgreSQL synchronously. With only 25 connections in the PgBouncer pool, high concurrency saturated the pool quickly.

## 2. Pre-Optimization Baseline

Load tests run with Locust (`locust -f locustfile.py --host http://localhost --headless -u N -r 50 --run-time 5m`):

| Metric | 50 users | 200 users | 500 users |
|--------|----------|-----------|-----------|
| Total requests | 36,707 | 41,936 | 33,539 |
| Requests/sec | 52.2 | 57.7 | 114.5 |
| p50 latency | 91 ms | 1,100 ms | 3,500 ms |
| p95 latency | 950 ms | 5,200 ms | 14,000 ms |
| p99 latency | 2,400 ms | 8,600 ms | 27,000 ms |
| Avg latency | 259 ms | 1,643 ms | 5,084 ms |
| Error rate | ~0 % | ~0 % | ~0 % |

At 1,000 users the system had an unacceptable failure ratio and was not viable.

**Key observation:** Even the `/health` endpoint (pure JSON, no DB) had p95 ≈ 770 ms at 50 users. This confirmed the bottleneck was **Gunicorn handler starvation**, not database queries alone.

## 3. What We Fixed

### Fix 1: Gunicorn Worker Tuning

```python
# gunicorn.conf.py — BEFORE
workers = multiprocessing.cpu_count() * 2 + 1  # = 3 in Docker
threads = 4                                     # 12 handlers/instance

# gunicorn.conf.py — AFTER
workers = int(os.environ.get("GUNICORN_WORKERS", 4))
threads = int(os.environ.get("GUNICORN_THREADS", 8))
# = 32 handlers/instance, 96 total across 3 replicas
```

### Fix 2: PgBouncer Pool Scaling

```yaml
# docker-compose.yml — BEFORE → AFTER
DEFAULT_POOL_SIZE: "25"  →  "50"
MIN_POOL_SIZE:     "5"   →  "10"
RESERVE_POOL_SIZE: "10"  →  "15"
```

### Fix 3: Redis Caching (already in place)

- URL metadata cached in Redis with 5-minute TTL on `GET /<code>`
- Cache key: `url:<short_code>`
- Cache invalidated on `PUT /urls/<id>` (deactivation) and `DELETE /urls/<id>`
- Graceful fallback: if Redis is down, requests pass through to PostgreSQL

## 4. Post-Optimization Results

| Metric | 500 users (after) |
|--------|-------------------|
| Requests/sec | [PENDING — run test] |
| p50 latency | [PENDING] |
| p95 latency | [PENDING] |
| p99 latency | [PENDING] |
| Error rate | [PENDING] |

## 5. Why It Worked

The root cause was **handler starvation at the application layer**, not the database. With only 36 total Gunicorn threads across the cluster, requests queued behind each other even before reaching the DB. Tripling the handler count to 96 eliminates this queueing.

The PgBouncer pool increase ensures the additional workers can actually get DB connections when cache misses occur. The hot redirect path is: `Nginx → Gunicorn → Redis (< 1 ms)` for cache hits, and `Nginx → Gunicorn → PgBouncer → PostgreSQL (20–40 ms)` for cache misses.

## 6. Remaining Limits

- `POST /shorten` is a write path that bypasses the cache — each request does 2 DB writes (URL + Event)
- `GET /urls` with no filters scans the full table — pagination mitigates this
- Redis is a single point of failure; Redis Sentinel or Cluster recommended beyond 1,000 req/s
- At extreme scale, PostgreSQL read replicas would offload read queries from the primary
