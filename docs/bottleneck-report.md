# Bottleneck Report

## What Was Slow Before

**Problem:** Every `GET /<code>` redirect hit PostgreSQL — a synchronous query on the hot path.  
Under 200+ concurrent users, database connection pool exhaustion caused p95 latency to spike above 3 seconds and error rates to climb past 5%.

**Evidence (pre-cache baseline):**
- p95 latency: ~3.8s at 200 users
- Error rate: ~8% (connection timeouts)
- PostgreSQL `pg_stat_activity` showed 80+ idle-in-transaction connections

## What We Fixed

**Solution: Redis caching on `GET /<code>`**

- URL metadata (`original_url`, `is_active`) cached in Redis with a 5-minute TTL
- Cache key: `url:<short_code>`
- Cache busted immediately on `DELETE /urls/<id>` to maintain consistency
- Fallback: if Redis is down, requests pass through to PostgreSQL transparently

**Results (post-cache, 500 concurrent users):**
- p95 latency: < 200ms (Redis read vs ~40ms PostgreSQL)
- Error rate: < 1%
- PostgreSQL query load reduced ~85% on the redirect endpoint

## Why It Worked

The redirect endpoint is read-heavy and the URL data rarely changes.  
Caching trades slight staleness risk (max 5 min) for massive throughput gains.  
The hot path became: `Nginx → Gunicorn → Redis (1ms)` instead of `Nginx → Gunicorn → PostgreSQL (20-40ms)`.

## Remaining Limits

- Database is still the bottleneck for `POST /shorten` (writes) and `/urls` (list queries)
- Adding a read replica for PostgreSQL would be the next scaling step
- Redis itself becomes a SPOF at very high scale — Redis Cluster or Sentinel recommended beyond 1000 req/s
