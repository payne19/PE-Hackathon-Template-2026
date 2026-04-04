from peewee import CharField, DateTimeField, ForeignKeyField, TextField

from app.database import BaseModel
from app.models.url import URL
from app.models.user import User


class Event(BaseModel):
    class Meta:
        table_name = "events"

    url = ForeignKeyField(URL, backref="events", null=True)
    user = ForeignKeyField(User, backref="events", null=True)
    event_type = CharField(max_length=50)
    timestamp = DateTimeField(null=True)
    details = TextField(null=True)
