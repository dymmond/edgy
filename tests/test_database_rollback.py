import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, drop_database=True, use_existing=False)
# we don't want drop_database/use_existing here
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

# Reference how to use database in tests with rollback


class MyModel(edgy.StrictModel):
    pass

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
    with models.database.force_rollback(True):
        async with models:
            yield


async def test_rollback1():
    assert await MyModel.query.all() == []
    assert bool(database.force_rollback())
    model = await MyModel.query.create()
    model2 = await MyModel.query.create()
    assert await MyModel.query.all() == [model, model2]


async def test_rollback2():
    assert await MyModel.query.all() == []
    assert bool(database.force_rollback())
    model = await MyModel.query.create()
    model2 = await MyModel.query.create()
    assert await MyModel.query.all() == [model, model2]
