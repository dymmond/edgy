import edgy
from edgy import Database, Registry


class MyRegistry(Registry):
    """
    Add logic unique to your registry or override
    existing functionality.
    """

    ...


database = Database("sqlite:///db.sqlite")
models = MyRegistry(database=database)


class User(edgy.Model):
    """
    The User model to be created in the database as a table
    If no name is provided the in Meta class, it will generate
    a "users" table for you.
    """

    id: int = edgy.IntegerField(primary_key=True)
    is_active: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models
