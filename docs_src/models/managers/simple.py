import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)
    email: str = edgy.EmailField(max_length=70)
    is_active: bool = edgy.BooleanField(default=True)

    class Meta:
        registry = models
        unique_together = [("name", "email")]


# Using ipython that supports await
# Don't use this in production! Use Alembic or any tool to manage
# The migrations for you
await models.create_all()  # noqa

await User.query.create(name="Edgy", email="foo@bar.com")  # noqa

user = await User.query.get(id=1)  # noqa
# User(id=1)
