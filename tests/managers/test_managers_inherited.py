from typing import ClassVar

import pytest

import edgy
from edgy import Manager
from edgy.core.db.querysets import QuerySet
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class ObjectsManager(Manager):
    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        if "is_active" in queryset.model_class.table.columns:
            queryset = queryset.filter(is_active=True)
        return queryset


class LanguageManager(Manager):
    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset().filter(language="EN")
        return queryset


class RatingManager(Manager):
    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset().filter(rating__gte=3)
        return queryset


class BaseModel(edgy.StrictModel):
    query: ClassVar[Manager] = ObjectsManager()
    languages: ClassVar[Manager] = LanguageManager()
    ratings: ClassVar[Manager] = RatingManager()
    non_inherited: ClassVar[Manager] = Manager(inherit=False)

    class Meta:
        registry = models


class User(BaseModel):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(BaseModel):
    name = edgy.CharField(max_length=100)
    rating = edgy.IntegerField(gte=1, lte=5)
    in_stock = edgy.BooleanField(default=False)
    is_active = edgy.BooleanField(default=False)


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


async def test_inherited_base_model_managers():
    assert "non_inherited" in BaseModel.meta.managers
    assert "non_inherited" not in User.meta.managers
    await User.query.create(name="test", language="EN")
    await User.query.create(name="test2", language="EN")
    await User.query.create(name="test3", language="PT")
    await User.query.create(name="test4", language="PT")

    users = await User.query.all()
    assert len(users) == 4

    users = await User.languages.all()
    assert len(users) == 2


@pytest.mark.parametrize(
    "manager,manager_class,total", [("query", ObjectsManager, 0), ("ratings", RatingManager, 3)]
)
async def test_inherited_base_model_managers_product(manager, manager_class, total):
    assert isinstance(getattr(Product, manager), manager_class)
    await Product.query.create(name="test", rating=5)
    await Product.query.create(name="test2", rating=4)
    await Product.query.create(name="test3", rating=3)
    await Product.query.create(name="test4", rating=2)
    await Product.query.create(name="test5", rating=2)
    await Product.query.create(name="test6", rating=1)

    products = await getattr(Product, manager).all()
    assert len(products) == total


async def test_raises_key_error_on_non_existing_field_for_product():
    await Product.query.create(name="test", rating=5)

    with pytest.raises(KeyError):
        await Product.languages.all()


async def test_raises_key_error_on_non_existing_field_for_user():
    await User.query.create(name="test", language="EN")

    with pytest.raises(KeyError):
        await User.ratings.all()
