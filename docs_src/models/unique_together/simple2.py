import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    name = edgy.CharField(max_length=255)
    email = edgy.EmailField(max_length=70)
    is_active = edgy.BooleanField(default=True)

    class Meta:
        registry = models
        unique_together = ["name"]  # or ("name",)
