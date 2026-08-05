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

database = DatabaseTestClient(DATABASE_URL, drop_database=True, use_existing=False)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


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
    price1: decimal.Decimal = fields.DecimalField(max_digits=9, decimal_places=2, ge=0, null=True)
    price2: decimal.Decimal = fields.DecimalField(
        max_digits=9, decimal_places=None, le=0, null=True
    )
    price3: decimal.Decimal = fields.DecimalField(
        max_digits=None, decimal_places=2, lt=100, null=True
    )
    price4: decimal.Decimal = fields.DecimalField(
        max_digits=2, decimal_places=2, ge=0, lt=1, null=True
    )
    price5: decimal.Decimal = fields.DecimalField(max_digits=3, decimal_places=2, gt=0, null=True)
    price6: decimal.Decimal = fields.DecimalField(max_digits=3, decimal_places=0, ge=0, null=True)
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


async def test_generate_some_left_parametrized():
    factory = ProductFactory()
    [factory.build(parameters={"price5": {"left_digits": 0}}, save=True) for i in range(10)]
    [factory.build(parameters={"price5": {"left_digits": 1}}, save=True) for i in range(10)]


async def test_generate_some_right_parametrized():
    factory = ProductFactory()
    [
        factory.build(
            parameters={"price1": {"right_digits": 0}, "price5": {"right_digits": 0}}, save=True
        )
        for i in range(10)
    ]
    [factory.build(parameters={"price1": {"right_digits": 1}}, save=True) for i in range(10)]
