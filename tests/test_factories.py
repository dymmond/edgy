import decimal
from datetime import date, datetime
from enum import Enum
from inspect import isawaitable
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
    price1: decimal.Decimal = fields.DecimalField(max_digits=9, decimal_places=2, null=True)
    price2: decimal.Decimal = fields.DecimalField(max_digits=9, decimal_places=None, null=True)
    price3: decimal.Decimal = fields.DecimalField(max_digits=None, decimal_places=2, null=True)
    status: str = fields.ChoiceField(StatusEnum, default=StatusEnum.DRAFT)
    value: float = fields.FloatField(null=True)

    class Meta:
        registry = models


class ProductFactory(ModelFactory):
    class Meta:
        model = Product


async def test_generate_some_save_implicit():
    factory = ProductFactory()
    inputs = [factory.build(save=True) for i in range(100)]
    assert all(not isawaitable(inp) for inp in inputs)


async def test_generate_some_save_bulk():
    factory = ProductFactory()
    inputs = [factory.build() for i in range(100)]
    await Product.query.bulk_create(inputs)


async def test_generate_some_save():
    factory = ProductFactory()
    inputs = [await factory.build().save() for i in range(100)]
    assert all(not isawaitable(inp) for inp in inputs)
