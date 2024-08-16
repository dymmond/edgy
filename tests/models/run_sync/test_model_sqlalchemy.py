import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)
    rating = edgy.IntegerField(minimum=1, maximum=5)
    in_stock = edgy.BooleanField(default=False)

    class Meta:
        registry = models
        name = "products"


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
    await models.drop_all()


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
