import pytest

import edgy
from edgy.contrib.permissions import BasePermission
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, use_existing=False)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class User(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100, unique=True)

    class Meta:
        registry = models


class Permission(BasePermission):
    users = edgy.fields.ManyToMany("User", through_tablename=edgy.NEW_M2M_NAMING)

    class Meta:
        registry = models
        unique_together = [("name",)]

    @classmethod
    def get_description(cls, field, instance, owner=None) -> str:
        return instance.name.upper()

    @classmethod
    def set_description(cls, field, instance, value) -> None:
        instance.__dict__["test"] = value


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback(True):
        async with models:
            yield


async def test_permission():
    permission = await Permission.query.create(name="View")
    assert permission.description == "VIEW"
    permission.description = "toll"
    assert permission.test == "toll"


async def test_querying():
    user = await User.query.create(name="edgy")
    permission = await Permission.query.create(users=[user], name="view")
    assert await Permission.query.users("view").get() == user
    assert await Permission.query.users("edit").count() == 0
    assert await Permission.query.permissions_of(user).get() == permission
