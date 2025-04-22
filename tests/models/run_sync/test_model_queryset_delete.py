import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class Product(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    rating = edgy.IntegerField(gte=1, lte=5)
    in_stock = edgy.BooleanField(default=False)

    class Meta:
        registry = models
        name = "products"


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


async def test_queryset_delete():
    shirt = edgy.run_sync(Product.query.create(name="Shirt", rating=5))
    edgy.run_sync(Product.query.create(name="Belt", rating=5))
    edgy.run_sync(Product.query.create(name="Tie", rating=5))

    edgy.run_sync(Product.query.filter(pk=shirt.id).delete())
    assert edgy.run_sync(Product.query.count()) == 2

    edgy.run_sync(Product.query.delete())
    assert edgy.run_sync(Product.query.count()) == 0
