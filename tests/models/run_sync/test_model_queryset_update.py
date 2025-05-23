import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


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


async def test_queryset_update():
    shirt = edgy.run_sync(Product.query.create(name="Shirt", rating=5))
    tie = edgy.run_sync(Product.query.create(name="Tie", rating=5))

    edgy.run_sync(Product.query.filter(pk=shirt.id).update(rating=3))
    shirt = edgy.run_sync(Product.query.get(pk=shirt.id))
    assert shirt.rating == 3
    assert edgy.run_sync(Product.query.get(pk=tie.id)) == tie

    edgy.run_sync(Product.query.update(rating=3))
    tie = edgy.run_sync(Product.query.get(pk=tie.id))
    assert tie.rating == 3


async def test_model_update_or_create():
    user, created = edgy.run_sync(
        User.query.update_or_create(name="Test", language="English", defaults={"name": "Jane"})
    )
    assert created is True
    assert user.name == "Jane"
    assert user.language == "English"

    user, created = edgy.run_sync(
        User.query.update_or_create(name="Jane", language="English", defaults={"name": "Test"})
    )
    assert created is False
    assert user.name == "Test"
    assert user.language == "English"
