import uuid

import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    non_default_id = edgy.BigIntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=255, primary_key=True)
    age: int = edgy.IntegerField(gte=18)
    is_active: bool = edgy.BooleanField(default=True)

    class Meta:
        registry = models
