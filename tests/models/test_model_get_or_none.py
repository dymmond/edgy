import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
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


async def test_get_or_none():
    user = await User.query.create(name="Charles")
    query = User.query.filter(name="Charles")
    assert user == await query.get()
    assert query._cache_count == 1
    assert query._cache_first == user
    assert query._cache_last == user

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
