import pytest

import edgy
from edgy.testing import DatabaseTestClient
from edgy.testing.factory import ModelFactory, SubFactory
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    rating: int = edgy.IntegerField(gte=1, lte=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)
    user: User = edgy.fields.ForeignKey(User)

    class Meta:
        registry = models


class Item(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    product = edgy.fields.ForeignKey(Product)

    class Meta:
        registry = models


class UserFactory(ModelFactory):
    class Meta:
        model = User

    name = "John Doe"
    language = "en"


class ProductFactory(ModelFactory):
    class Meta:
        model = Product

    name = "Product 1"
    rating = 5
    in_stock = True
    user = SubFactory("tests.factory.generation.test_basic_factory.UserFactory")


class ItemFactory(ModelFactory):
    class Meta:
        model = Item

    product = SubFactory("tests.factory.generation.test_basic_factory.ProductFactory")


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models.database:
        yield


async def test_can_use_sub_factories():
    product = ProductFactory().build()

    assert product.user.name == "John Doe"
    assert product.user.language == "en"
    assert product.name == "Product 1"
    assert product.rating == 5
    assert product.in_stock is True


async def test_nested_sub_factories():
    item = ItemFactory().build()

    assert item.product.user.name == "John Doe"
    assert item.product.user.language == "en"
    assert item.product.name == "Product 1"
    assert item.product.rating == 5
    assert item.product.in_stock is True


async def test_override_fields():
    user = UserFactory(name="Edgy").build()
    product = ProductFactory(name="Product 2", rating=3, user=user, in_stock=False).build()
    item = ItemFactory(product=product).build()

    # For user
    assert product.user.name == user.name

    # For product
    assert product.name == "Product 2"
    assert product.rating == 3
    assert product.in_stock is False

    # For item
    assert item.product.name == product.name
    assert item.product.rating == product.rating
    assert item.product.in_stock is False


async def test_save_in_db():
    user = await UserFactory(name="Edgy").build_and_save()
    product = await ProductFactory(
        name="Product 2", rating=3, user=user, in_stock=False
    ).build_and_save()
    item = await ItemFactory(product=product).build_and_save()

    assert product.user.id == user.id
    assert item.product.id == product.id

    total_users = await User.query.all()
    total_products = await Product.query.all()
    total_items = await Item.query.all()

    assert len(total_users) == 1
    assert len(total_products) == 1
    assert len(total_items) == 1
