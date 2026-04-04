from peewee import CharField, DateTimeField

from app.database import BaseModel


class User(BaseModel):
    class Meta:
        table_name = "users"

    username = CharField(unique=True, max_length=255)
    email = CharField(unique=True, max_length=255)
    created_at = DateTimeField(null=True)
