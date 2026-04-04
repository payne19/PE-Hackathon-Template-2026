from peewee import CharField, DateTimeField
from app.database import BaseModel


class User(BaseModel):
    class Meta:
        table_name = "users"

    username = CharField()
    email = CharField(unique=True)
    created_at = DateTimeField()
