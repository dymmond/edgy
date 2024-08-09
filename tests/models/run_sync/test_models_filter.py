import pytest

import edgy
from edgy.exceptions import ObjectNotFound
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(edgy.Model):
    name = edgy.CharField(max_length=100)
    rating = edgy.IntegerField(minimum=1, maximum=5)
    in_stock = edgy.BooleanField(default=False)
    user = edgy.ForeignKey(User, null=True, on_delete=edgy.CASCADE)

    class Meta:
        registry = models
        name = "products"


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_filter_with_foreign_key():
    user = edgy.run_sync(User.query.create(name="Adam"))

    for _ in range(5):
        edgy.run_sync(Product.query.create(name="sku", user=user, rating=4))

    products = edgy.run_sync(Product.query.filter(user=user))

    assert len(products) == 5
    products = edgy.run_sync(Product.query.filter(user__id=user.pk))

    assert len(products) == 5


async def test_model_filter():
    edgy.run_sync(User.query.create(name="Test"))
    edgy.run_sync(User.query.create(name="Jane"))
    edgy.run_sync(User.query.create(name="Lucy"))

    user = edgy.run_sync(User.query.get(name="Lucy"))
    assert user.name == "Lucy"

    with pytest.raises(ObjectNotFound):
        edgy.run_sync(User.query.get(name="Jim"))

    edgy.run_sync(Product.query.create(name="T-Shirt", rating=5, in_stock=True))
    edgy.run_sync(Product.query.create(name="Dress", rating=4))
    edgy.run_sync(Product.query.create(name="Coat", rating=3, in_stock=True))

    product = edgy.run_sync(Product.query.get(name__iexact="t-shirt", rating=5))
    assert product.pk is not None
    assert product.name == "T-Shirt"
    assert product.rating == 5

    products = edgy.run_sync(Product.query.all(rating__gte=2, in_stock=True))
    assert len(products) == 2

    products = edgy.run_sync(Product.query.all(name__icontains="T"))
    assert len(products) == 2

    # Test escaping % character from icontains, contains, and iexact
    edgy.run_sync(Product.query.create(name="100%-Cotton", rating=3))
    edgy.run_sync(Product.query.create(name="Cotton-100%-Egyptian", rating=3))
    edgy.run_sync(Product.query.create(name="Cotton-100%", rating=3))
    products = Product.query.filter(name__iexact="100%-cotton")
    assert edgy.run_sync(products.count()) == 1

    products = Product.query.filter(name__contains="%")
    assert edgy.run_sync(products.count()) == 3

    products = Product.query.filter(name__icontains="%")
    assert edgy.run_sync(products.count()) == 3

    products = Product.query.exclude(name__iexact="100%-cotton")
    assert edgy.run_sync(products.count()) == 5

    products = Product.query.exclude(name__contains="%")
    assert edgy.run_sync(products.count()) == 3

    products = Product.query.exclude(name__icontains="%")
    assert edgy.run_sync(products.count()) == 3


async def test_model_nested_filter():
    edgy.run_sync(User.query.create(name="Test", language="EN"))
    edgy.run_sync(User.query.create(name="Test", language="ES"))
    edgy.run_sync(User.query.create(name="Test", language="PT"))
    edgy.run_sync(User.query.create(name="Jane", language="ES"))
    edgy.run_sync(User.query.create(name="Lucy", language="PT"))

    users = edgy.run_sync(User.query.filter(name="Test").filter(language="EN"))

    assert len(users) == 1

    users = edgy.run_sync(
        User.query.filter(name="Test").filter(language="EN").filter(language="PT")
    )

    assert len(users) == 0
