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

    id = saffier.IntegerField(primary_key=True)
    is_active = saffier.BooleanField(default=False)

    class Meta:
        registry = models
