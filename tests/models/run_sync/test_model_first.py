import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
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


async def test_model_first():
    Test = edgy.run_sync(User.query.create(name="Test"))
    jane = edgy.run_sync(User.query.create(name="Jane"))

    assert edgy.run_sync(User.query.first()) == Test
    assert edgy.run_sync(User.query.first(name="Jane")) == jane
    assert edgy.run_sync(User.query.filter(name="Jane").first()) == jane
    assert edgy.run_sync(User.query.filter(name="Lucy").first()) is None
