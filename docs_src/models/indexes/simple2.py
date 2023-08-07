import edgy
from edgy import Database, Index, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)
    email: str = edgy.EmailField(max_length=70)
    is_active: bool = edgy.BooleanField(default=True)

    class Meta:
        registry = models
        indexes = [Index(fields=["email"])]
