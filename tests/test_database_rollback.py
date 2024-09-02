import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, drop_database=True, use_existing=False)
# we don't want drop_database/use_existing here
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

# Reference how to use database in tests with rollback


class MyModel(edgy.Model):
    pass

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        await models.drop_all()


@pytest.fixture()
async def rollback_transactions():
    async with models.database:
        yield


async def test_rollback1(rollback_transactions):
    assert await MyModel.query.all() == []
    assert bool(database.force_rollback())
    model = await MyModel.query.create()
    assert await MyModel.query.all() == [model]


async def test_rollback2(rollback_transactions):
    assert await MyModel.query.all() == []
    assert bool(database.force_rollback())
    model = await MyModel.query.create()
    assert await MyModel.query.all() == [model]
