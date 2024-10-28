import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    """
    The user model representation
    """

    name: str = edgy.CharField(max_length=255)
    age: int = edgy.IntegerField(minimum=18)
    is_active: bool = edgy.BooleanField(default=True)

    class Meta:
        registry = models
