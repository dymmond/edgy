import decimal
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

import pytest

import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from edgy.testing.factory import ModelFactory
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, force_rollback=False, drop_database=True)
models = edgy.Registry(database=database)


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with models:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


def time():
    return datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class Product(edgy.StrictModel):
    id: int = fields.IntegerField(primary_key=True, autoincrement=True)
    uuid: UUID = fields.UUIDField(null=True, unique=True)
    created: datetime = fields.DateTimeField(default=datetime.now)
    created_day: datetime = fields.DateField(default=date.today)
    created_time: datetime = fields.TimeField(default=time)
    created_date: datetime = fields.DateField(auto_now_add=True)
    created_datetime: datetime = fields.DateTimeField(auto_now_add=True)
    updated_datetime: datetime = fields.DateTimeField(auto_now=True)
    updated_date: datetime = fields.DateField(auto_now=True)
    data: dict[Any, Any] = fields.JSONField(default=dict)
    description: str = fields.CharField(null=True, max_length=255)
    huge_number: int = fields.BigIntegerField(default=0)
    price: decimal.Decimal = fields.DecimalField(max_digits=9, decimal_places=2, null=True)
    status: str = fields.ChoiceField(StatusEnum, default=StatusEnum.DRAFT)
    value: float = fields.FloatField(null=True)

    class Meta:
        registry = models


class ProductFactory(ModelFactory):
    class Meta:
        model = Product


@pytest.mark.parametrize("method", ["bulk_create", "bulk_update_or_create", "bulk_get_or_create"])
async def test_bulk_create_like(method):
    factory = ProductFactory(price=None, uuid=None)
    inputs = [factory.build(overwrites={"created_time": time()}) for i in range(100)]
    await getattr(Product.query, method)(inputs)


async def test_bulk_create_bulk_ignore():
    factory = ProductFactory(price=None, uuid=None)
    inputs = [factory.build(overwrites={"created_time": time()}) for i in range(100)]
    await Product.query.bulk_create(inputs, ignore_conflicts=True)


@pytest.mark.parametrize("rollback", [True, False])
@pytest.mark.parametrize("method", ["bulk_update", "bulk_update_or_create"])
async def test_bulk_update_like(method, rollback):
    factory = ProductFactory(price=None, uuid=None)
    await Product.query.bulk_create(
        [factory.build(overwrites={"created_time": time()}) for i in range(100)]
    )
    products1 = await Product.query.order_by("id").distinct()
    inputs2 = [
        factory.build(overwrites={"id": products1[i].id, "created_time": time()})
        for i in range(50)
    ]
    with database.force_rollback(rollback):
        products2 = await getattr(Product.query, method)(inputs2)
        products = await Product.query.order_by("id").distinct()
    assert len(products) == 100
    for i in range(100):
        if i < 50:
            assert (
                products[i] == products2[i][0] if isinstance(products2[i], tuple) else products2[i]
            )
        else:
            assert products[i] == products1[i]
