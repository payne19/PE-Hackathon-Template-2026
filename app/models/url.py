from peewee import BooleanField, CharField, DateTimeField, ForeignKeyField

from app.database import BaseModel
from app.models.user import User


class URL(BaseModel):
    class Meta:
        table_name = "urls"

    user = ForeignKeyField(User, backref="urls", null=True)
    short_code = CharField(unique=True, max_length=20)
    original_url = CharField(max_length=2048)
    title = CharField(null=True, max_length=255)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(null=True)
    updated_at = DateTimeField(null=True)
