import pytest

import edgy
from edgy.contrib.permissions import BasePermission
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, use_existing=False)
models = edgy.Registry(
    database=edgy.Database(database, force_rollback=True), with_content_type=True
)


class User(edgy.Model):
    name = edgy.fields.CharField(max_length=100)

    class Meta:
        registry = models


class Group(edgy.Model):
    name = edgy.fields.CharField(max_length=100)
    users = edgy.fields.ManyToMany("User", embed_through=False)

    class Meta:
        registry = models


class Permission(BasePermission):
    users = edgy.fields.ManyToMany("User", embed_through=False)
    groups = edgy.fields.ManyToMany("Group", embed_through=False)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models:
        yield


async def test_querying():
    user = await User.query.create(name="edgy")
    group = await Group.query.create(name="admin", users=[user])
    permission = await Permission.query.create(users=[user], name="view")
    permission2 = await Permission.query.create(groups=[group], name="admin")
    assert await Permission.query.filter(name="admin").get()
    assert await Permission.query.permissions_of(user).get(name="view") == permission
    permissions = await Permission.query.permissions_of(group)
    assert permissions == [permission2]
    assert await Permission.query.users("view").get() == user
    assert await Permission.query.users("admin").get() == user
    assert await Permission.query.users("edit").count() == 0
    assert await Permission.query.permissions_of(user).count() == 2
