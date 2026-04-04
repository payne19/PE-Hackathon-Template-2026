# Failure Modes Reference

This document describes every known failure scenario, what the system does automatically, and what a human must do to recover.

---

## 1. App Container Crashes

**What happens:**
- Docker detects the exit and restarts the container automatically (`restart: always` in `docker-compose.yml`).
- Nginx health-checks the upstream; while the container is restarting, Nginx routes traffic to the other two app instances (`app2`, `app3`).
- Users see no error — requests continue to be served.

**What the user sees:** Nothing. The service remains available.

**Recovery:** Automatic within seconds.

**To demo:**
```bash
docker compose kill app1
# immediately try: curl http://localhost/health  → {"status": "ok"}
docker compose ps   # app1 shows "restarting" then "running"
```

---

## 2. Database (PostgreSQL) Down

**What happens:**
- All requests that need the database return `500 Internal Server Error`.
- The response body is always JSON: `{"error": "Internal server error"}` — no stack trace is exposed.
- The error is logged at ERROR level with a full traceback in `docker compose logs`.
- When the database comes back up, Peewee reconnects automatically on the next request (no app restart needed).

**What the user sees:**
```json
{"error": "Internal server error"}
```

**Recovery:**
```bash
docker compose up -d db
# wait ~10 seconds for healthcheck, then requests succeed automatically
```

---

## 3. Redis Down

**What happens:**
- On startup, `init_cache()` in `app/cache.py` catches the connection error and falls back to `SimpleCache` (in-memory).
- Redirect lookups bypass cache and read directly from PostgreSQL.
- All other functionality works normally.

**What the user sees:** No visible change. Slightly higher latency on redirects.

**Recovery:** Automatic fallback. No action required. Redis reconnects when restored.

---

## 4. Sending Bad Input (Garbage Data)

**What happens:** Every endpoint validates input and returns a structured JSON error. The app never crashes or leaks a Python traceback.

| Input | Endpoint | Response |
|-------|----------|----------|
| Missing JSON body | `POST /shorten` | `400 {"error": "Request body must be JSON"}` |
| `original_url` is an integer | `POST /shorten` | `422 {"error": "original_url is required and must be a string"}` |
| URL without `http://` scheme | `POST /shorten` | `422 {"error": "original_url must start with http:// or https://"}` |
| Duplicate `short_code` | `POST /shorten` | `409 {"error": "short_code already in use"}` |
| Unknown short code | `GET /<code>` | `404 {"error": "Short code not found"}` |
| Deactivated short code | `GET /<code>` | `410 {"error": "URL has been deactivated"}` |
| Nonexistent resource | `GET /urls/999` | `404 {"error": "URL not found"}` |
| Missing `username` | `POST /users` | `422 {"error": "username must be a non-empty string"}` |
| Duplicate email | `POST /users` | `409 {"error": "Email already exists"}` |
| Wrong HTTP verb | `DELETE /health` | `405 {"error": "Method Not Allowed"}` |
| Route doesn't exist | `GET /doesnotexist` | `404 {"error": "Resource not found"}` |

**To demo:**
```bash
curl -s -X POST http://localhost/shorten \
  -H "Content-Type: application/json" \
  -d '{"original_url": 12345}'
# → {"error": "original_url is required and must be a string"}

curl -s http://localhost/zzz-no-such-code
# → {"error": "Short code not found"}
```

---

## 5. PGBouncer Down

**What happens:**
- `app1`, `app2`, `app3` cannot reach the database via the connection pool.
- Requests return `500` JSON errors (same as #2 above).
- Docker restarts PGBouncer automatically (`restart: always`).

**Recovery:** Automatic. Connections resume after PGBouncer restart.

---

## 6. Short Code Exhaustion (Extreme Edge Case)

**What happens:**
- The app tries 10 random 6-character codes. If all 10 happen to collide with existing codes, it returns:
  ```json
  {"error": "Could not generate unique short code"}
  ```
  with status `500`.

**Likelihood:** Essentially zero in practice (62^6 ≈ 56 billion combinations).

---

## 7. Unhandled Exception (Unknown Bug)

**What happens:**
- Flask's global `500` error handler catches all uncaught exceptions.
- Returns: `{"error": "Internal server error"}` — never a Python traceback.
- Full stack trace is written to logs: `docker compose logs app1 | grep ERROR`

**What the user sees:**
```json
{"error": "Internal server error"}
```

---

## Summary Table

| Failure | User Impact | Auto-Recovery | Manual Step |
|---------|-------------|---------------|-------------|
| App container crash | None (other instances serve) | Yes (`restart: always`) | None |
| All 3 app containers crash | 502 from Nginx | Yes (Docker restarts all) | None |
| PostgreSQL down | 500 on DB requests | Yes (reconnects on recovery) | `docker compose up -d db` |
| Redis down | Slightly slower redirects | Yes (falls back to SimpleCache) | None |
| PGBouncer down | 500 on DB requests | Yes (`restart: always`) | None |
| Bad input from client | 4xx JSON error | N/A | N/A |
| Unknown bug | 500 JSON error | No | Check logs, fix code |
