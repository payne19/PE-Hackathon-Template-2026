"""Seed the database from CSV files in the seeds/ directory."""
import csv
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from peewee import chunked  # noqa: E402

from app.database import db, init_db  # noqa: E402


class _FakeApp:
    config = {}

    def before_request(self, f):
        return f

    def teardown_appcontext(self, f):
        return f


def _init():
    import app.models  # noqa: F401

    fake = _FakeApp()
    init_db(fake)


def _load_users(seeds_dir: Path):
    from app.models.user import User

    path = seeds_dir / "users.csv"
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    with db.atomic():
        for batch in chunked(rows, 200):
            User.insert_many(
                [
                    {
                        "id": r["id"],
                        "username": r["username"],
                        "email": r["email"],
                        "created_at": r["created_at"] or None,
                    }
                    for r in batch
                ]
            ).on_conflict_ignore().execute()
    valid_ids = {u.id for u in User.select(User.id)}
    print(f"  Loaded {len(valid_ids)} users (skipped {len(rows) - len(valid_ids)} duplicates)")
    return valid_ids


def _load_urls(seeds_dir: Path, valid_user_ids: set):
    from app.models.url import URL

    path = seeds_dir / "urls.csv"
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    with db.atomic():
        for batch in chunked(rows, 200):
            URL.insert_many(
                [
                    {
                        "id": r["id"],
                        "user_id": int(r["user_id"]) if r["user_id"] and int(r["user_id"]) in valid_user_ids else None,
                        "short_code": r["short_code"],
                        "original_url": r["original_url"],
                        "title": r["title"] or None,
                        "is_active": r["is_active"].strip().lower() in ("true", "1", "yes"),
                        "created_at": r["created_at"] or None,
                        "updated_at": r["updated_at"] or None,
                    }
                    for r in batch
                ]
            ).on_conflict_ignore().execute()
    print(f"  Loaded {len(rows)} URLs")


def _load_events(seeds_dir: Path, valid_user_ids: set):
    from app.models.event import Event
    from app.models.url import URL

    path = seeds_dir / "events.csv"
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    valid_url_ids = {u.id for u in URL.select(URL.id)}

    with db.atomic():
        for batch in chunked(rows, 200):
            Event.insert_many(
                [
                    {
                        "id": r["id"],
                        "url_id": int(r["url_id"]) if r["url_id"] and int(r["url_id"]) in valid_url_ids else None,
                        "user_id": int(r["user_id"]) if r["user_id"] and int(r["user_id"]) in valid_user_ids else None,
                        "event_type": r["event_type"],
                        "timestamp": r["timestamp"] or None,
                        "details": r["details"] or None,
                    }
                    for r in batch
                ]
            ).on_conflict_ignore().execute()
    print(f"  Loaded {len(rows)} events")


def main():
    seeds_dir = Path(__file__).parent / "seeds"
    _init()

    from app.models.user import User
    from app.models.url import URL
    from app.models.event import Event

    db.create_tables([User, URL, Event], safe=True)
    print("Tables ensured.")

    print("Truncating tables...")
    db.execute_sql("TRUNCATE TABLE events, urls, users RESTART IDENTITY CASCADE")

    print("Loading users...")
    valid_ids = _load_users(seeds_dir)
    print("Loading URLs...")
    _load_urls(seeds_dir, valid_ids)
    print("Loading events...")
    _load_events(seeds_dir, valid_ids)

    print("Resetting sequences...")
    db.execute_sql("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))")
    db.execute_sql("SELECT setval('urls_id_seq', (SELECT MAX(id) FROM urls))")
    db.execute_sql("SELECT setval('events_id_seq', (SELECT MAX(id) FROM events))")

    print("Done!")


if __name__ == "__main__":
    main()
