from uuid import UUID

import pytest

import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class Product(edgy.StrictModel):
    id: int = fields.IntegerField(primary_key=True, autoincrement=True)
    uuid: UUID = fields.UUIDField(null=True)

    class Meta:
        table_prefix = "test"
        registry = models


class InheritProduct(Product):
    name: str = fields.CharField(null=True, max_length=255)

    class Meta:
        registry = models


class ABSModel(edgy.StrictModel):
    id: int = fields.IntegerField(primary_key=True, autoincrement=True)

    class Meta:
        abstract = True
        registry = models
        table_prefix = "abs"


class InheritABSModel(ABSModel):
    name: str = fields.CharField(null=True, max_length=255)

    class Meta:
        registry = models


class SecondInheritABSModel(InheritABSModel):
    description: str = fields.CharField(null=True, max_length=255)

    class Meta:
        registry = models


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


async def test_table_prefix():
    assert Product.table.name == "test_products"
    assert InheritProduct.table.name == "test_inheritproducts"
    assert InheritABSModel.table.name == "abs_inheritabsmodels"
    assert SecondInheritABSModel.table.name == "abs_secondinheritabsmodels"
