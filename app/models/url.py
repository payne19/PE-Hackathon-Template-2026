import secrets
import string
from datetime import datetime, timezone

from peewee import BooleanField, CharField, DateTimeField, ForeignKeyField, IntegerField

from app.database import BaseModel

BASE62 = string.ascii_letters + string.digits 


def generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(BASE62) for _ in range(length))


class User(BaseModel):
    username = CharField(unique=True, max_length=64)
    email = CharField(unique=True, max_length=255)
    password_hash = CharField(max_length=255)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "users"


class URL(BaseModel):
    original_url = CharField(max_length=2048)
    short_code = CharField(unique=True, max_length=16, index=True)
    user = ForeignKeyField(User, backref="urls", null=True, on_delete="SET NULL")
    is_active = BooleanField(default=True)
    click_count = IntegerField(default=0)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "urls"
