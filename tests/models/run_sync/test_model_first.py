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
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback():
        async with models:
            yield


async def test_model_first():
    Test = edgy.run_sync(User.query.create(name="Test"))
    jane = edgy.run_sync(User.query.create(name="Jane"))

    assert edgy.run_sync(User.query.first()) == Test
    assert edgy.run_sync(User.query.filter(name="Jane").first()) == jane
    assert edgy.run_sync(User.query.filter(name="Lucy").first()) is None
