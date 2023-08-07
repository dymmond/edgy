import uuid

import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255, primary_key=True, default=str(uuid.uuid4))
    age: int = edgy.IntegerField(minimum=18)
    is_active: bool = edgy.BooleanField(default=True)

    class Meta:
        registry = models
