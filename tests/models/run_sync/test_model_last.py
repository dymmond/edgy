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
    async with database:
        await models.create_all()
        yield
    await models.drop_all()


async def test_model_last():
    Test = edgy.run_sync(User.query.create(name="Test"))
    jane = edgy.run_sync(User.query.create(name="Jane"))

    assert edgy.run_sync(User.query.last()) == jane
    assert edgy.run_sync(User.query.filter(name="Jane").last()) == jane
    assert edgy.run_sync(User.query.filter(name="Test").last()) == Test
    assert edgy.run_sync(User.query.filter(name="Lucy").last()) is None
