"""Run this script once to create all database tables."""
from dotenv import load_dotenv

load_dotenv()

from app.database import db
from app.models import User, Url, Event
from peewee import PostgresqlDatabase
import os

database = PostgresqlDatabase(
    os.environ.get("DATABASE_NAME", "hackathon_db"),
    host=os.environ.get("DATABASE_HOST", "localhost"),
    port=int(os.environ.get("DATABASE_PORT", 5432)),
    user=os.environ.get("DATABASE_USER", "postgres"),
    password=os.environ.get("DATABASE_PASSWORD", "postgres"),
)
db.initialize(database)

with database:
    database.create_tables([User, Url, Event], safe=True)
    print("Tables created: users, urls, events")
