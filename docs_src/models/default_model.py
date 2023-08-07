import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    age = edgy.IntegerField(minimum=18)
    is_active = edgy.BooleanField(default=True)

    class Meta:
        registry = models
