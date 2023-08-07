import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.Model):
    """
    If the `tablename` is not declared in the `Meta`,
    saffier will pluralise the class name.

    This table will be called in the database `users`.
    """

    name = saffier.CharField(max_length=255)
    is_active = saffier.BooleanField(default=True)

    class Meta:
        registry = models
