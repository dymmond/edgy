from typing import ClassVar

import pytest

import edgy
from edgy import Manager
from edgy.core.db.querysets import QuerySet
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, test_prefix="")
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class ActiveManager(Manager):
    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset().filter(is_active=True)
        return queryset


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(edgy.Model):
    active: ClassVar[Manager] = ActiveManager()

    name = edgy.CharField(max_length=100)
    rating = edgy.IntegerField(minimum=1, maximum=5)
    in_stock = edgy.BooleanField(default=False)
    is_active = edgy.BooleanField(default=False)

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


async def test_model_crud():
    users = await User.query.all()
    assert User.query.instance is None
    assert users == []

    user = await User.query.create(name="Test")
    assert User.query.instance is None
    assert user.query.instance is user
    users = await User.query.all()
    assert user.name == "Test"
    assert user.pk is not None
    assert users == [user]

    lookup = await User.query.get()
    assert lookup == user

    await user.update(name="Jane")
    users = await User.query.all()
    assert user.name == "Jane"
    assert user.pk is not None
    assert users == [user]

    await user.delete()
    users = await User.query.all()
    assert users == []


async def test_model_crud_different_manager():
    products = await Product.active.all()
    assert products == []

    await Product.query.create(name="One", in_stock=True, is_active=False, rating=5)
    await Product.query.create(name="Two", in_stock=True, is_active=False, rating=2)
    product = await Product.query.create(name="Three", in_stock=True, is_active=True, rating=3)

    products = await Product.query.all()
    assert len(products) == 3

    products = await Product.active.all()
    assert len(products) == 1

    assert products[0].pk == product.pk
