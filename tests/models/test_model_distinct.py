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


@pytest.mark.skipif(database.url.dialect == "mysql", reason="Not supported on MySQL")
@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_distinct():
    await Product.query.create(name="test", rating=5, in_stock=True)
    await Product.query.create(name="test", rating=4, in_stock=True)
    await Product.query.create(name="test", rating=2, in_stock=True)

    products = await Product.query.distinct("name").all()
    assert len(products) == 1

    products = await Product.query.distinct("rating").all()
    assert len(products) == 3

    products = await Product.query.distinct("name", "in_stock").all()
    assert len(products) == 1

    products = await Product.query.distinct("in_stock").all()
    assert len(products) == 1

    products = await Product.query.distinct("rating", "in_stock").all()
    assert len(products) == 3


@pytest.mark.skipif(database.url.dialect == "mysql", reason="Not supported on MySQL")
@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_distinct_two_without_all():
    await Product.query.create(name="test", rating=5, in_stock=True)
    await Product.query.create(name="test", rating=4, in_stock=True)
    await Product.query.create(name="test", rating=2, in_stock=True)

    products = await Product.query.distinct("name")
    assert len(products) == 1

    products = await Product.query.distinct("rating")
    assert len(products) == 3

    products = await Product.query.distinct("name", "in_stock")
    assert len(products) == 1

    products = await Product.query.distinct("in_stock")
    assert len(products) == 1

    products = await Product.query.distinct("rating", "in_stock")
    assert len(products) == 3
