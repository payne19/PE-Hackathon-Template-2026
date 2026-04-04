# Scalability Quest

## Architecture Overview

```
                    ┌─────────┐
    Locust ────────►│  Nginx  │  (load balancer, least_conn)
                    └────┬────┘
                ┌────────┼────────┐
                ▼        ▼        ▼
            ┌──────┐ ┌──────┐ ┌──────┐
            │ App1 │ │ App2 │ │ App3 │  Gunicorn (4 workers × 8 threads each)
            └──┬───┘ └──┬───┘ └──┬───┘
               │        │        │
          ┌────┴────────┴────────┴────┐
          ▼                           ▼
     ┌─────────┐               ┌───────────┐
     │  Redis  │ (cache)       │ PgBouncer │ (conn pool)
     └─────────┘               └─────┬─────┘
                                     ▼
                               ┌───────────┐
                               │ PostgreSQL│
                               └───────────┘
```

**Stack:** Flask + Gunicorn (gthread) → Nginx (least_conn) → 3 app replicas → PgBouncer → PostgreSQL 16, Redis 7 for caching.

---

## 🥉 Bronze Tier: Baseline

### Objective
Prove the application works end-to-end with CI, health checks, and basic observability.

### Evidence
- `/health` returns `{"status": "ok"}` (200)
- CI pipeline runs 106 tests with 84%+ coverage
- JSON-structured logging on all requests (method, path, status, latency_ms)
- Prometheus metrics exposed at `/metrics`

### Load Test (50 users)
```bash
docker compose up --build -d
locust -f locustfile.py --host http://localhost \
  --headless -u 50 -r 10 --run-time 5m
```

| Metric | Value |
|--------|-------|
| Concurrent users | **50** |
| Total requests | 36,707 |
| Requests/sec | 52.2 |
| p50 latency | 91 ms |
| p95 latency | 950 ms |
| p99 latency | 2,400 ms |
| Error rate | **~0 %** |

### Screenshots
- `screenshots/bronze-health-check.png` — Health endpoint returning 200
- `screenshots/bronze-ci-green.png` — CI pipeline passing

---

## 🥈 Silver Tier: Scale Out

### Objective
Handle 200 concurrent users by scaling horizontally with Docker Compose and a load balancer.

### What We Added
- **3 app replicas** behind Nginx with `least_conn` balancing
- **PgBouncer** connection pooling in transaction mode
- **Persistent upstream connections** (`keepalive 64`) between Nginx and app servers

### Load Test (200 users)
```bash
locust -f locustfile.py --host http://localhost \
  --headless -u 200 -r 25 --run-time 5m
```

| Metric | Value |
|--------|-------|
| Concurrent users | **200** |
| Total requests | 41,936 |
| Requests/sec | 57.7 |
| p50 latency | 1,100 ms |
| p95 latency | 5,200 ms |
| p99 latency | 8,600 ms |
| Error rate | **~0 %** |

> **Note:** These are pre-optimization numbers. High latencies at 200 users prompted the investigation in the [Bottleneck Report](bottleneck-report.md).

### Screenshots
- `screenshots/silver-locust-200-users.png` — Locust dashboard at 200 users

---

## 🥇 Gold Tier: The Speed of Light

### Objective
Handle 500+ concurrent users with < 5% error rate through caching and architectural optimization.

### What We Added
- **Redis caching** on `GET /<code>` with 5-minute TTL and cache invalidation on writes
- **Graceful degradation** — Redis failure falls back to PostgreSQL transparently
- **Gunicorn tuning** — Fixed worker count to 4 workers × 8 threads = 32 handlers/instance (was 3 × 4 = 12 due to Docker `cpu_count()` returning 1)
- **PgBouncer pool scaling** — DEFAULT_POOL_SIZE 25 → 50, MIN_POOL_SIZE 5 → 10

### Load Test (500 users) — Pre-Optimization
```bash
locust -f locustfile.py --host http://localhost \
  --headless -u 500 -r 50 --run-time 5m
```

| Metric | Before Optimization |
|--------|---------------------|
| Concurrent users | **500** |
| Total requests | 33,539 |
| Requests/sec | 114.5 |
| p50 latency | 3,500 ms |
| p95 latency | 14,000 ms |
| p99 latency | 27,000 ms |
| Error rate | **~0 %** |

### Load Test (500 users) — Post-Optimization

| Metric | After Optimization |
|--------|-------------------|
| Concurrent users | **500** |
| Requests/sec | [PENDING — run test] |
| p50 latency | [PENDING] |
| p95 latency | [PENDING] |
| p99 latency | [PENDING] |
| Error rate | [PENDING] |

### Stretch Test (1,000 users)

We pushed beyond the 500-user target to find our ceiling:

```bash
locust -f locustfile.py --host http://localhost \
  --headless -u 1000 -r 100 --run-time 5m
```

| Metric | Value |
|--------|-------|
| Concurrent users | **1,000** |
| Requests/sec | [PENDING] |
| p95 latency | [PENDING] |
| Error rate | [PENDING] |

### Screenshots
- `screenshots/gold-locust-500-users.png` — Locust dashboard at 500 users
- `screenshots/gold-locust-1000-users.png` — Stretch test at 1,000 users
- `screenshots/gold-response-times.png` — Response time chart
- `screenshots/gold-error-rate.png` — Error rate staying under 5%

---

## Optimization Summary

| Tier | Users | RPS | p95 | Error % | Key Changes |
|------|-------|-----|-----|---------|-------------|
| Bronze | **50** | 52.2 | 950 ms | ~0 % | Baseline (single Gunicorn, direct DB) |
| Silver | **200** | 57.7 | 5,200 ms | ~0 % | + 3 replicas, Nginx LB, PgBouncer |
| Gold (before) | **500** | 114.5 | 14,000 ms | ~0 % | + Redis caching on hot path |
| Gold (after) | **500** | [PENDING] | [PENDING] | [PENDING] | + Gunicorn 4w×8t, PgBouncer pool 50 |
| Stretch | **1,000** | [PENDING] | [PENDING] | [PENDING] | Same stack, stress ceiling |

---

## How to Reproduce

```bash
# Start the full stack
docker compose up --build -d

# Bronze (50 users)
locust -f locustfile.py --host http://localhost --headless -u 50 -r 10 --run-time 5m

# Silver (200 users)
locust -f locustfile.py --host http://localhost --headless -u 200 -r 25 --run-time 5m

# Gold (500 users)
locust -f locustfile.py --host http://localhost --headless -u 500 -r 50 --run-time 5m

# Stretch (1000 users)
locust -f locustfile.py --host http://localhost --headless -u 1000 -r 100 --run-time 5m
```
