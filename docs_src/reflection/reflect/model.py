import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    age = edgy.IntegerField(minimum=18, null=True)
    is_active = edgy.BooleanField(default=True, null=True)
    description = edgy.CharField(max_length=255, null=True)
    profile_type = edgy.CharField(max_length=255, null=True)
    username = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
