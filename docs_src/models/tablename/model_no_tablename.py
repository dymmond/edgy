import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    """
    If the `tablename` is not declared in the `Meta`,
    edgy will pluralise the class name.

    This table will be called in the database `users`.
    """

    name: str = edgy.CharField(max_length=255)
    is_active: bool = edgy.BooleanField(default=True)

    class Meta:
        registry = models
