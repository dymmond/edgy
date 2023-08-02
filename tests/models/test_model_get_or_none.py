import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_get_or_none():
    user = await User.query.create(name="Charles")
    assert user == await User.query.filter(name="Charles").get()

    user = await User.query.get_or_none(name="Luigi")
    assert user is None

    user = await User.query.get_or_none(name="Charles")
    assert user.pk == 1


async def test_get_or_none_without_get():
    user = await User.query.create(name="Charles")
    users = await User.query.filter(name="Charles")
    assert user == users[0]

    user = await User.query.get_or_none(name="Luigi")
    assert user is None

    user = await User.query.get_or_none(name="Charles")
    assert user.pk == 1
