import edgy

database = edgy.Database("sqlite:///db.sqlite")
registry = edgy.Registry(database=database)


class User(edgy.Model):
    id: int = edgy.BigIntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=255)
    email: str = edgy.CharField(max_length=255)
    is_verified: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = registry
