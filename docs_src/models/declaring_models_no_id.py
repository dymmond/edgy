import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    """
    The user model representation.

    The `id` is not provided and Saffier will automatically
    generate a primary_key `id` BigIntegerField.
    """

    name = edgy.CharField(max_length=255)
    age = edgy.IntegerField(minimum=18)
    is_active = edgy.BooleanField(default=True)

    class Meta:
        registry = models
