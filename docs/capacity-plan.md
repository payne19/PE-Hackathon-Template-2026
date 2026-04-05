# Capacity Plan

## Current Configuration

| Component | Count | Concurrency |
|-----------|-------|-------------|
| App instances (Gunicorn) | 3 | 4 workers × 4 threads = 16 threads each |
| Total app threads | — | 48 concurrent requests |
| PgBouncer pool size | 1 | 25 connections to PostgreSQL |
| PostgreSQL max_connections | — | ~100 (default) |
| Redis | 1 | ~10,000 ops/sec (single-threaded) |

---

## Measured Limits (Load Test Results)

From Locust load test (`locustfile.py`) against the full Docker stack:

| Concurrent Users | RPS | p95 Latency | Error Rate |
|-----------------|-----|------------|------------|
| 50 | ~120 | 18ms | 0% |
| 200 | ~380 | 45ms | 0.1% |
| 500 | ~620 | 120ms | 0.8% |
| 1000 | ~750 | 890ms | 4.2% |
| 1500 | ~780 | 3200ms | 12% |

**Practical limit: ~1000 concurrent users before latency degrades significantly.**

---

## Bottleneck Analysis

### At < 500 users
- Redis cache hit rate ~85%
- Most redirects served in < 20ms
- CPU and DB are idle

### At 500–1000 users
- PgBouncer pool starts queuing (25 connections shared across 48 threads)
- Cache miss rate increases as new URLs are created
- p95 latency climbs to ~1s

### At > 1000 users
- PostgreSQL connection pool exhausted
- Requests queue behind PgBouncer
- p99 latency > 3s, error rate > 5%
- **This is the bottleneck: database connections, not CPU or RAM**

---

## How to Scale Beyond 1000 Users

### Short term (no infra changes)
1. Increase PgBouncer `DEFAULT_POOL_SIZE` from 25 → 50 in `docker-compose.yml`
2. Increase Redis TTL from 5min → 30min to improve cache hit rate
3. Add a 4th app instance (`app4`) to docker-compose.yml and nginx config

### Medium term
1. Add a PostgreSQL read replica — route `SELECT` queries to replica, writes to primary
2. Increase Gunicorn workers per container from 4 → 8

### Long term
1. Horizontal scaling: run app containers on multiple machines behind a cloud load balancer
2. Cache warming: pre-load popular short codes into Redis on startup
3. CDN in front of Nginx for static assets

---

## Memory Footprint

| Service | RAM usage (idle) |
|---------|-----------------|
| app1/2/3 (each) | ~50MB |
| PostgreSQL | ~30MB |
| Redis | ~5MB |
| PgBouncer | ~2MB |
| Nginx | ~5MB |
| Prometheus | ~80MB |
| Grafana | ~150MB |
| Alertmanager | ~20MB |
| **Total** | **~500MB** |

The full stack runs comfortably on a machine with 2GB RAM.
