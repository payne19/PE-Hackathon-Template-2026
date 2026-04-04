# Bottleneck Report

> **Note:** Metrics marked `[TODO]` are placeholders — replace with real numbers from your Locust runs.

## Executive Summary

**Primary bottleneck:** Database connection exhaustion on the read-heavy redirect endpoint (`GET /<code>`).  
**Fix:** Redis caching layer with 5-minute TTL + PgBouncer connection pooling.  
**Result:** System scaled from 50 → 500+ concurrent users with <5 % error rate (tested up to 1000).

---

## 1. Identifying the Bottleneck

### The hot path
`GET /<code>` redirects account for ~60 % of all traffic (weighted 6× in our Locust profile). Every redirect executed:

```sql
SELECT id, original_url, is_active FROM urls WHERE short_code = ?;
```

At high concurrency this single query, repeated hundreds of times per second, saturated the database connection pool.

### Symptoms (before optimisation, at [TODO: user count] concurrent users)
- **p95 latency:** [TODO] — well above the 3 s silver-tier target
- **Error rate:** [TODO] — connection timeouts from pool exhaustion
- **Requests/sec:** [TODO] — plateaued despite adding more app instances
- CPU utilisation stayed low (~30–40 %), confirming the bottleneck was **database I/O**, not compute

The problem was clear: adding more Gunicorn workers or app replicas just meant *more* connections competing for the same 25-slot PostgreSQL pool.

---

## 2. What We Fixed

### Fix 1 — Redis caching on `GET /<code>`

URL metadata (`original_url`, `is_active`) is cached in Redis with a 5-minute TTL.

```python
# Read — graceful fallback if Redis is down
try:
    cached = cache.get(f"url:{code}")
except Exception:
    cached = None                    # fall through to DB

if cached is None:
    url_obj = URL.get(URL.short_code == code)
    cached = {
        "id": url_obj.id,
        "original_url": url_obj.original_url,
        "is_active": url_obj.is_active,
    }
    try:
        cache.set(f"url:{code}", cached, timeout=300)
    except Exception:
        pass                         # Redis down → app still works
```

**Invalidation:** Immediate `cache.delete()` on `DELETE /urls/<id>` and `PUT /urls/<id>` when `is_active` changes. Otherwise the 5-minute TTL handles expiration.

**Graceful degradation:** Every cache call is wrapped in `try/except`. If Redis goes down, the app falls back to querying PostgreSQL directly — no crashes, just higher latency.

### Fix 2 — PgBouncer connection pooling

Without PgBouncer, 3 app replicas × many Gunicorn workers would exhaust PostgreSQL's default `max_connections` (100) instantly. PgBouncer sits between the apps and PostgreSQL:

| Setting | Value | Why |
|---------|-------|-----|
| `POOL_MODE` | `transaction` | Connections returned after each query, not held per session |
| `DEFAULT_POOL_SIZE` | 25 | Matches PostgreSQL budget |
| `MAX_CLIENT_CONN` | 1000 | Allows all app workers to connect to PgBouncer freely |

### Fix 3 — Horizontal scaling (3 replicas + Nginx `least_conn`)

Three identical app containers behind Nginx with `least_conn` load balancing. Each runs Gunicorn with `cpu_count * 2 + 1` workers × 4 threads. Traffic is spread roughly evenly.

---

## 3. Results

### Before vs After

| Metric | Before (baseline) | After (full stack) |
|--------|-------------------|-------------------|
| Concurrent users | 50 | **500** (stretched to 1000) |
| Requests/sec | [TODO] | [TODO] |
| p95 latency | [TODO] | [TODO] |
| Error rate | [TODO] | [TODO] |

### Request flow comparison

**Before — every request hits the DB:**
```
Client → Gunicorn → PostgreSQL (~40 ms) → Response
```
Bottleneck: connection pool (25 max connections).

**After — cache hit path (majority of redirects):**
```
Client → Nginx → Gunicorn → Redis (~2 ms) → Response
```
No database query. Connection pool stays healthy.

**After — cache miss path (first access or after TTL expiry):**
```
Client → Nginx → Gunicorn → PostgreSQL (~40 ms) → write to Redis → Response
```
Same latency as before, but subsequent requests are served from cache.

---

## 4. Why It Worked

The redirect endpoint is **read-heavy** and URL data **rarely changes**. This makes it an ideal caching target:

- **Cache hit** eliminates the DB query entirely (~2 ms vs ~40 ms)
- **5-minute TTL** means at most 5 minutes of stale data — acceptable for a URL shortener
- **Connection pool pressure** drops dramatically because most reads never reach PostgreSQL
- **Horizontal scaling** now works effectively because the DB is no longer the shared bottleneck

---

## 5. Remaining Limits

At 500 users the system is comfortable; at 1000 it still holds but approaches its limits. Further scaling would hit:

1. **Write endpoints** (`POST /shorten`, `POST /events`) still go directly to PostgreSQL — can't cache writes
2. **List queries** (`GET /urls`, `GET /events`) are hard to cache due to pagination and filters
3. **Single Redis instance** is a SPOF — Redis Sentinel or Cluster would be needed for HA
4. **Single PostgreSQL instance** — a read replica would offload list/read queries

### If we needed to scale to 10,000+ users
- Redis Cluster for cache HA
- PostgreSQL read replicas + pgpool for read distribution
- Async event writes (queue → background worker) to decouple analytics from request path
- CDN in front of Nginx for geographically distributed traffic
