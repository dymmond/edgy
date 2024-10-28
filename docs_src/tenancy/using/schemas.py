import edgy
from edgy import Database, Registry

database = Database("<YOUR-CONNECTION-STRING>")
models = Registry(database=database)


class User(edgy.Model):
    is_active: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models
