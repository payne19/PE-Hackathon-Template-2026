# API Reference

Base URL: `http://localhost` (via Nginx) or `http://localhost:5000` (direct)

---

## Health

### `GET /health`
Returns service liveness.

**Response 200**
```json
{ "status": "ok" }
```

---

## Metrics

### `GET /metrics`
Prometheus-format metrics (request counts, latency histograms, error rates).

---

## URL Shortener

### `POST /shorten`
Create a short URL.

**Request body** (JSON)
| Field | Type | Required | Description |
|---|---|---|---|
| `original_url` | string | ✅ | Must start with `http://` or `https://` |
| `title` | string | ❌ | Human-readable label |
| `short_code` | string | ❌ | Custom code (6–20 chars). Auto-generated if omitted. |
| `user_id` | integer | ❌ | Associate with an existing user |

**Responses**
| Status | Meaning |
|---|---|
| 201 | Created — returns URL object |
| 400 | Non-JSON body |
| 409 | `short_code` already in use |
| 422 | Validation error (missing/invalid `original_url`) |

**Example**
```bash
curl -X POST http://localhost/shorten \
  -H 'Content-Type: application/json' \
  -d '{"original_url": "https://github.com", "title": "GitHub"}'
```
```json
{
  "id": 1,
  "short_code": "aB3xYz",
  "original_url": "https://github.com",
  "title": "GitHub",
  "is_active": true,
  "user_id": null,
  "created_at": "2026-04-03T20:00:00+00:00",
  "updated_at": "2026-04-03T20:00:00+00:00"
}
```

---

### `GET /<code>`
Redirect to the original URL.

**Responses**
| Status | Meaning |
|---|---|
| 302 | Redirect to `original_url` |
| 404 | Short code not found |
| 410 | URL exists but has been deactivated |

**Example**
```bash
curl -L http://localhost/aB3xYz
```

---

### `GET /urls`
List all active URLs (paginated).

**Query params**
| Param | Default | Max |
|---|---|---|
| `page` | 1 | — |
| `per_page` | 20 | 100 |

**Response 200**
```json
{
  "total": 1500,
  "page": 1,
  "per_page": 20,
  "results": [ { ...url object... } ]
}
```

---

### `GET /urls/<id>`
Get a single URL by database ID.

**Responses**: 200 with URL object, 404 if not found.

---

### `DELETE /urls/<id>`
Deactivate a URL (soft-delete). Clears Redis cache for that code.

**Responses**: 200 with `{"message": "URL deactivated", "id": <id>}`, 404 if not found.

---

### `GET /stats/<code>`
Click stats for a short code.

**Response 200**
```json
{
  "short_code": "aB3xYz",
  "original_url": "https://github.com",
  "title": "GitHub",
  "is_active": true,
  "click_count": 42,
  "created_at": "2026-04-03T20:00:00+00:00"
}
```

**Responses**: 200 with stats object, 404 if code not found.

---

## Error Format

All errors return JSON — never HTML stack traces.

```json
{ "error": "Short code not found" }
```
