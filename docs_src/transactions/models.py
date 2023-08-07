import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.Model):
    """
    The User model to be created in the database as a table
    If no name is provided the in Meta class, it will generate
    a "users" table for you.
    """

    email = saffier.EmailField(unique=True, max_length=120)
    is_active = saffier.BooleanField(default=False)

    class Meta:
        registry = models


class Profile(saffier.Model):
    user = saffier.ForeignKey(User, on_delete=saffier.CASCADE)

    class Meta:
        registry = models
