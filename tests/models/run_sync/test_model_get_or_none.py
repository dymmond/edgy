import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
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
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_get_or_none_without_get():
    user = edgy.run_sync(User.query.create(name="Charles"))
    assert user == edgy.run_sync(User.query.filter(name="Charles").get())

    user = edgy.run_sync(User.query.get_or_none(name="Luigi"))
    assert user is None

    user = edgy.run_sync(User.query.get_or_none(name="Charles"))
    assert user.pk == 1


async def test_get_or_none():
    user = edgy.run_sync(User.query.create(name="Charles"))
    users = edgy.run_sync(User.query.filter(name="Charles"))
    assert user == users[0]

    user = edgy.run_sync(User.query.get_or_none(name="Luigi"))
    assert user is None

    user = edgy.run_sync(User.query.get_or_none(name="Charles"))
    assert user.pk == 1
