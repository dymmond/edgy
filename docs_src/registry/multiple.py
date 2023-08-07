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
    is_active = edgy.BooleanField(default=False)

    class Meta:
        registry = models


another_db = Database("postgressql://user:password@localhost:5432/mydb")
another_registry = MyRegistry(another_db=another_db)


class Profile(edgy.Model):
    is_active = edgy.BooleanField(default=False)

    class Meta:
        registry = another_registry
