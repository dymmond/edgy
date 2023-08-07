import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.Model):
    """
    The user model representation.

    The `id` is not provided and Saffier will automatically
    generate a primary_key `id` BigIntegerField.
    """

    name = saffier.CharField(max_length=255)
    age = saffier.IntegerField(minimum=18)
    is_active = saffier.BooleanField(default=True)

    class Meta:
        registry = models
