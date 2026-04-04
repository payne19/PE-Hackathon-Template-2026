"""Load seed data from CSV files into the database."""
import csv
import os
from dotenv import load_dotenv

load_dotenv()

from app.database import db
from app.models import User, URL, Event
from peewee import PostgresqlDatabase

database = PostgresqlDatabase(
    os.environ.get("DATABASE_NAME", "hackathon_db"),
    host=os.environ.get("DATABASE_HOST", "localhost"),
    port=int(os.environ.get("DATABASE_PORT", 5432)),
    user=os.environ.get("DATABASE_USER", "postgres"),
    password=os.environ.get("DATABASE_PASSWORD", "postgres"),
)
db.initialize(database)

SEED_DIR = os.path.join(os.path.dirname(__file__), "seeds")


def load_users():
    path = os.path.join(SEED_DIR, "users.csv")
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            User.get_or_create(
                id=int(row["id"]),
                defaults={
                    "username": row["username"],
                    "email": row["email"],
                    "created_at": row["created_at"],
                },
            )
    print(f"Users seeded from {path}")


def load_urls():
    path = os.path.join(SEED_DIR, "urls.csv")
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            URL.get_or_create(
                id=int(row["id"]),
                defaults={
                    "user_id": int(row["user_id"]),
                    "short_code": row["short_code"],
                    "original_url": row["original_url"],
                    "title": row["title"] or None,
                    "is_active": row["is_active"].lower() in ("1", "true", "yes"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                },
            )
    print(f"URLs seeded from {path}")


def load_events():
    path = os.path.join(SEED_DIR, "events.csv")
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            Event.get_or_create(
                id=int(row["id"]),
                defaults={
                    "url_id": int(row["url_id"]),
                    "user_id": int(row["user_id"]),
                    "event_type": row["event_type"],
                    "timestamp": row["timestamp"],
                    "details": row.get("details") or None,
                },
            )
    print(f"Events seeded from {path}")


if __name__ == "__main__":
    with database:
        load_users()
        load_urls()
        load_events()
    print("Seed complete.")
