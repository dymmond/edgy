import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class MyModel(edgy.StrictModel):
    name: str = edgy.CharField(max_length=150)
    weight: float = edgy.FloatField(default=0.0)

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


async def test_defaults():
    model = (await MyModel.query.get_or_create(name="01", defaults={"weight": 30}))[0]
    assert model.weight == 30
    assert model.name == "01"
    await MyModel.query.filter(name="01").update(name="02")
    model2 = await MyModel.query.get(name="02")
    assert model2.weight == 30
