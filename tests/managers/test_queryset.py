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


class ActiveManager(Manager):
    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset().filter(is_active=True)
        return queryset


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    active: ClassVar[Manager] = ActiveManager()

    name = edgy.CharField(max_length=100)
    rating = edgy.IntegerField(gte=1, lte=5)
    in_stock = edgy.BooleanField(default=False)
    is_active = edgy.BooleanField(default=False)

    class Meta:
        registry = models
        name = "products"


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


async def test_contains():
    users = await User.query.all()
    assert users == []

    user = await User.query.create(name="Test")

    exists = await User.query.contains(user)

    assert exists is True


async def test_contains_false():
    users = await User.query.all()
    assert users == []

    user = await User.query.create(name="Test")

    exists = await Product.query.contains(user)

    assert exists is False
