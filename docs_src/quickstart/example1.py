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


# Create the db and tables
# Don't use this in production! Use Alembic or any tool to manage
# The migrations for you
await models.create_all()  # noqa

await User.query.create(is_active=False)  # noqa

user = await User.query.get(id=1)  # noqa
print(user)
# User(id=1)
