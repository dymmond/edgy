import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.ReflectModel):
    age: int = edgy.IntegerField(minimum=18)
    is_active: bool = edgy.BooleanField(default=True)

    class Meta:
        tablename = "users"
        registry = models
