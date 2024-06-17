from typing import ClassVar

import edgy
from edgy import Database, Manager, QuerySet, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class InactiveManager(Manager):
    """
    Custom manager that will return only active users
    """

    def get_queryset(self) -> "QuerySet":
        queryset = super().get_queryset().filter(is_active=False)
        return queryset


class Team(edgy.Model):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)
    email: str = edgy.EmailField(max_length=70)
    team = edgy.ForeignKey(Team, null=True, related_name="members")
    is_active: bool = edgy.BooleanField(default=True)

    # Add the new manager only for related queries
    query_related: ClassVar[Manager] = InactiveManager()

    class Meta:
        registry = models
        unique_together = [("name", "email")]

# Using ipython that supports await
# Don't use this in production! Use Alembic or any tool to manage
# The migrations for you
await models.create_all()  # noqa

# Create a Team using the default manager
team = await Team.query.create(name="Edgy team")  # noqa

# Create an inactive user
user1 = await User.query.create(name="Edgy", email="foo@bar.com", is_active=False, team=team)  # noqa

# You can also create a user using the new manager
user2 = await User.query_related.create(name="Another Edgy", email="bar@foo.com", is_active=False, team=team)  # noqa

# Create a user using the default manager
user3 =await User.query.create(name="Edgy", email="user@edgy.com", team=team)  # noqa


# Querying them all
users = await User.query.all()  # noqa
assert [user1, user2, user3] == users
# now with team
users2 = await team.members.all()  # noqa
assert [user1, user2] == users2
