from decimal import Decimal

import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class MyModel(edgy.StrictModel):
    price = edgy.DecimalField(decimal_places=2)
    name: str = edgy.CharField(max_length=255)

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


async def test_inplace_updates():
    obj1 = await MyModel.query.create(price=Decimal(10), name="foo")
    obj2 = await MyModel.query.create(price=Decimal(20), name="bar")
    await MyModel.query.update(
        price=MyModel.table.c.price + Decimal(3), name=MyModel.table.c.name + "postfix"
    )
    await obj1.load()
    await obj2.load()
    assert obj1.price == 13
    assert obj2.price == 23
