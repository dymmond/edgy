import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.testclient import DatabaseTestClient as Database

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL)
models = edgy.Registry(database=database)


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_meta_tablename():
    await User.query.create(name="edgy")
    users = await User.query.all()

    assert len(users) == 1

    user = await User.query.get(name="edgy")

    assert user.meta.tablename == "users"


async def test_meta_registry():
    await User.query.create(name="edgy")
    users = await User.query.all()

    assert len(users) == 1

    user = await User.query.get(name="edgy")

    assert user.meta.registry == models
