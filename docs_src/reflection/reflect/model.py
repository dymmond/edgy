import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    age: int = edgy.IntegerField(minimum=18, null=True)
    is_active: bool = edgy.BooleanField(default=True, null=True)
    description: str = edgy.CharField(max_length=255, null=True)
    profile_type: str = edgy.CharField(max_length=255, null=True)
    username: str = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
