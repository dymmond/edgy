import enum

import pytest

import edgy
from edgy.testing import DatabaseTestClient
from edgy.testing.factory import FactoryField, ModelFactory
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, force_rollback=True)
models = edgy.Registry(database=database)


class ProductType(enum.Enum):
    real = "real"
    virtual = "virtual"


class ProductRef(edgy.ModelRef):
    __related_name__ = "products_set"


class User(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    product_ref = edgy.fields.RefForeignKey(ProductRef, null=True)

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    rating: int = edgy.IntegerField(minimum=1, maximum=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)
    user: User = edgy.fields.ForeignKey(User)
    type: ProductType = edgy.fields.ChoiceField(choices=ProductType, default=ProductType.virtual)

    class Meta:
        registry = models
        name = "products"


class Cart(edgy.StrictModel):
    products = edgy.fields.ManyToMany(Product)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    async with models:
        yield


async def test_can_save():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

        product_ref = FactoryField(parameters={"min": 5, "max": 5})

    user = UserFactory().build(save=True)
    new_user = await User.query.get(id=user.id)
    assert user == new_user
    assert await new_user.products_set.count() == 5
    product = await new_user.products_set.first()
    assert product.user == user


async def test_can_build_and_save():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

        product_ref = FactoryField(parameters={"min": 5, "max": 5})

    user = await UserFactory().build_and_save()
    new_user = await User.query.get(id=user.id)
    assert user == new_user
    assert await new_user.products_set.count() == 5
    product = await new_user.products_set.first()
    assert product.user == user


async def test_can_build_and_save_not_with_save():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

    with pytest.raises(TypeError):
        await UserFactory().build_and_save(save=True)
