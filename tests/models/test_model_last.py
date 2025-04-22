import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


async def test_model_last():
    Test = await User.query.create(name="Test")
    jane = await User.query.create(name="Jane")

    query = User.query.all()
    assert query._cache_last is None
    assert await query.last() == jane
    assert query._cache_last is not None
    assert await User.query.filter(name="Jane").last() == jane
    assert await User.query.filter(name="Test").last() == Test
    assert await User.query.filter(name="Lucy").last() is None
