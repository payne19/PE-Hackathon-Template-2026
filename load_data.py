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

    User.delete().execute()
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
            ).execute()
    print(f"  Loaded {len(rows)} users")


def _load_urls(seeds_dir: Path):
    from app.models.url import URL

    path = seeds_dir / "urls.csv"
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    URL.delete().execute()
    with db.atomic():
        for batch in chunked(rows, 200):
            URL.insert_many(
                [
                    {
                        "id": r["id"],
                        "user_id": r["user_id"] or None,
                        "short_code": r["short_code"],
                        "original_url": r["original_url"],
                        "title": r["title"] or None,
                        "is_active": r["is_active"].strip().lower() in ("true", "1", "yes"),
                        "created_at": r["created_at"] or None,
                        "updated_at": r["updated_at"] or None,
                    }
                    for r in batch
                ]
            ).execute()
    print(f"  Loaded {len(rows)} URLs")


def _load_events(seeds_dir: Path):
    from app.models.event import Event

    path = seeds_dir / "events.csv"
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    Event.delete().execute()
    with db.atomic():
        for batch in chunked(rows, 200):
            Event.insert_many(
                [
                    {
                        "id": r["id"],
                        "url_id": r["url_id"] or None,
                        "user_id": r["user_id"] or None,
                        "event_type": r["event_type"],
                        "timestamp": r["timestamp"] or None,
                        "details": r["details"] or None,
                    }
                    for r in batch
                ]
            ).execute()
    print(f"  Loaded {len(rows)} events")


def main():
    seeds_dir = Path(__file__).parent / "seeds"
    _init()

    from app.models.user import User
    from app.models.url import URL
    from app.models.event import Event

    db.create_tables([User, URL, Event], safe=True)
    print("Tables ensured.")

    print("Loading users...")
    _load_users(seeds_dir)
    print("Loading URLs...")
    _load_urls(seeds_dir)
    print("Loading events...")
    _load_events(seeds_dir)
    print("Done!")


if __name__ == "__main__":
    main()
