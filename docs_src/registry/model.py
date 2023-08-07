import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    """
    The User model to be created in the database as a table
    If no name is provided the in Meta class, it will generate
    a "users" table for you.
    """

    id = edgy.IntegerField(primary_key=True)
    is_active = edgy.BooleanField(default=False)

    class Meta:
        registry = models
