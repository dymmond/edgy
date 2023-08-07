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

    email: str = edgy.EmailField(unique=True, max_length=120)
    is_active: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models


class Profile(edgy.Model):
    user: User = edgy.ForeignKey(User, on_delete=edgy.CASCADE)

    class Meta:
        registry = models
