import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, test_prefix="")
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


async def test_model_count():
    edgy.run_sync(User.query.create(name="Test"))
    edgy.run_sync(User.query.create(name="Jane"))
    edgy.run_sync(User.query.create(name="Lucy"))

    assert edgy.run_sync(User.query.count()) == 3
    assert edgy.run_sync(User.query.filter(name__icontains="T").count()) == 1
