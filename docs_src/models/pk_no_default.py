import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    id: int = edgy.CharField(max_length=255, primary_key=True)
    age: int = edgy.IntegerField(minimum=18)
    is_active: bool = edgy.BooleanField(default=True)

    class Meta:
        registry = models
