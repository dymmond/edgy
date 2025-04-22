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
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback(True):
        async with models:
            yield


async def test_model_sqlalchemy_filter_operators():
    user = edgy.run_sync(User.query.create(name="George"))

    assert user == edgy.run_sync(User.query.filter(User.columns.name == "George").get())
    assert user == edgy.run_sync(User.query.filter(User.columns.name.is_not(None)).get())
    assert user == edgy.run_sync(
        User.query.filter(User.columns.name.startswith("G"))
        .filter(User.columns.name.endswith("e"))
        .get()
    )

    # not not =  ==
    assert user == edgy.run_sync(User.query.exclude(User.columns.name != "George").get())

    shirt = edgy.run_sync(Product.query.create(name="100%-Cotton", rating=3))
    assert shirt == edgy.run_sync(
        Product.query.filter(Product.columns.name.contains("Cotton")).get()
    )


async def test_model_sqlalchemy_filter_operators_no_get():
    user = edgy.run_sync(User.query.create(name="George"))
    users = edgy.run_sync(User.query.filter(User.columns.name == "George"))
    assert user == users[0]

    users = edgy.run_sync(User.query.filter(User.columns.name.is_not(None)))
    assert user == users[0]

    users = edgy.run_sync(
        User.query.filter(User.columns.name.startswith("G")).filter(
            User.columns.name.endswith("e")
        )
    )
    assert user == users[0]

    # not not =  ==
    assert user == edgy.run_sync(User.query.exclude(User.columns.name != "George").get())

    shirt = edgy.run_sync(Product.query.create(name="100%-Cotton", rating=3))
    shirts = edgy.run_sync(Product.query.filter(Product.columns.name.contains("Cotton")))
    assert shirt == shirts[0]
