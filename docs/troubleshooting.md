# Troubleshooting Guide

Real bugs hit during the hackathon and how they were fixed.

---

## 1. `pytest-cov` not found — tests fail immediately

**Symptom:**
```
ERROR: unrecognized arguments: --cov=app
```

**Cause:** `uv sync --dev` installed a different set of packages than expected.

**Fix:**
```bash
pip install pytest-cov
# or
uv pip install pytest-cov
```

---

## 2. SQLite test DB path fails on Windows

**Symptom:**
```
sqlite3.OperationalError: unable to open database file: /tmp/hackathon_test.db
```

**Cause:** `/tmp/` doesn't exist on Windows.

**Fix:** Use `tempfile.gettempdir()` for cross-platform path:
```python
import tempfile
path = os.path.join(tempfile.gettempdir(), "hackathon_test.db")
```

---

## 3. PostgreSQL not reachable locally

**Symptom:**
```
peewee.OperationalError: could not connect to server
```

**Cause:** PostgreSQL service not running, or wrong host/port in `.env`.

**Fix:**
```bash
# Check if postgres is running
docker compose ps db

# If not running
docker compose up -d db

# Verify connection
docker compose exec db pg_isready -U postgres
```

---

## 4. Merge conflicts after `git merge origin/main`

**Symptom:** VS Code shows conflict markers in `app/routes/__init__.py` and other files.

**Cause:** Teammate merged a large PR while we were working on the same files.

**Fix:** Accept the incoming changes for framework files, then re-add our custom routes on top:
```bash
git checkout --theirs app/routes/__init__.py
# Then manually re-add missing blueprint registrations
```

---

## 5. `/shorten` returns 500 on integer `original_url`

**Symptom:**
```python
AttributeError: 'NoneType' object has no attribute 'strip'
```

**Cause:** `data.get("original_url", "").strip()` crashes when value is not a string.

**Fix:** Validate type before calling `.strip()`:
```python
raw_url = data.get("original_url")
if not isinstance(raw_url, str) or not raw_url.strip():
    return jsonify(error="original_url is required"), 422
```

---

## 6. Bulk CSV import crashes on duplicate username

**Symptom:**
```
peewee.IntegrityError: duplicate key value violates unique constraint "user_username"
```

**Cause:** `User.get_or_create()` matched on `email` but the `username` already existed from a different row.

**Fix:** Use `INSERT ... ON CONFLICT` to upsert:
```python
User.insert(username=row["username"], email=row["email"])
    .on_conflict(conflict_target=[User.username], preserve=[User.email])
    .execute()
```

---

## 7. Evaluator tests dropping from 27 to 22

**Symptom:** CI evaluator score dropped after merging.

**Cause:** Merge removed 3 endpoints that the evaluator tests:
- `POST /events`
- `DELETE /users/<id>`
- `GET /events?event_type=` filter

**Fix:** Restore the missing endpoints from git history:
```bash
git show <last-good-commit>:app/routes/events.py
git show <last-good-commit>:app/routes/users.py
```

---

## 8. Discord alerts not firing

**Symptom:** Alertmanager shows alert firing, Discord channel receives nothing.

**Cause 1:** Slack-compatible Discord URL format (`/slack` suffix) doesn't work with Alertmanager's slack_configs.

**Fix 1:** Use a dedicated Discord bridge container:
```yaml
alertmanager-discord:
  image: benjojo/alertmanager-discord
  environment:
    DISCORD_WEBHOOK: "https://discordapp.com/api/webhooks/..."
```

**Cause 2:** Alert already fired before bridge was ready — `repeat_interval: 1h` prevented retry.

**Fix 2:** Reduce `repeat_interval` to `2m` for testing, then restart Alertmanager.

---

## 9. Docker container won't auto-restart after `docker stop`

**Symptom:** `restart: always` set but container stays stopped.

**Cause:** `docker compose stop` / `docker compose kill` are treated as intentional stops — Docker does not restart on manual stop.

**Fix:** Use `docker kill <container-id>` directly to simulate a crash, which does trigger `restart: always`.

---

## 10. Coverage below 70%

**Symptom:**
```
FAIL Required test coverage of 70% not reached. Total coverage: 56%
```

**Cause:** New routes (users, events) had no tests.

**Fix:** Add test files for each new route. Run `pytest --cov=app --cov-report=term-missing` to see exactly which lines are uncovered.
