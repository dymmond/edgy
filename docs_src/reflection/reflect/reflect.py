import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Profile(edgy.ReflectModel):
    is_active: bool = edgy.BooleanField(default=True, null=True)
    profile_type: str = edgy.CharField(max_length=255, null=True)
    username: str = edgy.CharField(max_length=255, null=True)

    class Meta:
        tablename = "users"
        registry = models
