import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Profile(edgy.ReflectModel):
    is_active = edgy.BooleanField(default=True, null=True)
    profile_type = edgy.CharField(max_length=255, null=True)
    username = edgy.CharField(max_length=255, null=True)

    class Meta:
        tablename = "users"
        registry = models
