import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.Model):
    """
    The user model representation
    """

    id = saffier.IntegerField(primary_key=True)
    name = saffier.CharField(max_length=255)
    age = saffier.IntegerField(minimum=18)
    is_active = saffier.BooleanField(default=True)

    class Meta:
        registry = models
