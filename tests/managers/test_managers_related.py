from typing import ClassVar

import pytest

import edgy
from edgy import Manager
from edgy.core.db.querysets import QuerySet
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class InactiveManager(Manager):
    """
    Custom manager that will return only active users
    """

    def get_queryset(self) -> "QuerySet":
        queryset = super().get_queryset().filter(is_active=False)
        return queryset


class Team(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class User(edgy.StrictModel):
    name: str = edgy.CharField(max_length=255)
    email: str = edgy.EmailField(max_length=70)
    team = edgy.ForeignKey(Team, null=True, related_name="members")
    is_active: bool = edgy.BooleanField(default=True)

    # Add the new manager only for related queries
    query_related: ClassVar[Manager] = InactiveManager()

    class Meta:
        registry = models
        unique_together = [("name", "email")]


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models.database:
        yield


async def test_managers_related():
    # Create a Team using the default manager
    team = await Team.query.create(name="Edgy team")  # noqa

    # Create an inactive user
    user1 = await User.query.create(name="Edgy", email="foo@bar.com", is_active=False, team=team)  # noqa

    # You can also create a user using the new manager
    user2 = await User.query_related.create(
        name="Another Edgy", email="bar@foo.com", is_active=False, team=team
    )  # noqa

    # Create a user using the default manager
    user3 = await User.query.create(name="Edgy", email="user@edgy.com", team=team)  # noqa

    # Querying them all
    users = await User.query.all()  # noqa
    assert [user1, user2, user3] == users
    # now with team
    users2 = await team.members.all()  # noqa
    assert [user1, user2] == users2
