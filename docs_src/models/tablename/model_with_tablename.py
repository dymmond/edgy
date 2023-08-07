import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)
    is_active: bool = edgy.BooleanField(default=True)

    class Meta:
        tablename = "users"
        registry = models
