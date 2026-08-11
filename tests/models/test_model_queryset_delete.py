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
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


async def test_queryset_delete():
    shirt = await Product.query.create(name="Shirt", rating=5)
    await Product.query.create(name="Belt", rating=5)
    await Product.query.create(name="Tie", rating=5)

    await Product.query.filter(pk=shirt.id).delete()
    assert await Product.query.count() == 2

    await Product.query.delete()
    assert await Product.query.count() == 0


async def test_queryset_delete_cache():
    queryset = Product.query.all()
    await queryset.create(name="Belt", rating=5)
    await queryset.create(name="Tie", rating=5)
    assert queryset._cache
    assert await queryset.delete()
    assert not queryset._cache


async def test_queryset_no_delete_cache():
    await Product.query.create(name="Belt", rating=5)
    await Product.query.create(name="Tie", rating=5)
    queryset = Product.query.filter(name="test")
    await queryset
    assert queryset._cache_count == 0
    assert queryset._cache_fetch_all
    await queryset.delete()
    assert queryset._cache_count == 0
    assert queryset._cache_fetch_all
