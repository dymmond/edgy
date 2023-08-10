import decimal
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict
from uuid import UUID

import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient as Database

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL)
models = edgy.Registry(database=database, schema="mamas")


def time():
    return datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class Product(edgy.Model):
    id: int = fields.IntegerField(primary_key=True)
    uuid: UUID = fields.UUIDField(null=True)
    created: datetime = fields.DateTimeField(default=datetime.now)
    created_day: datetime = fields.DateField(default=date.today)
    created_time: datetime = fields.TimeField(default=time)
    created_date: datetime = fields.DateField(auto_now_add=True)
    created_datetime: datetime = fields.DateTimeField(auto_now_add=True)
    updated_datetime: datetime = fields.DateTimeField(auto_now=True)
    updated_date: datetime = fields.DateField(auto_now=True)
    data: Dict[Any, Any] = fields.JSONField(default={})
    description: str = fields.CharField(null=True, max_length=255)
    huge_number: int = fields.BigIntegerField(default=0)
    price: decimal.Decimal = fields.DecimalField(null=True)
    status: str = fields.ChoiceField(StatusEnum, default=StatusEnum.DRAFT)
    value: float = fields.FloatField(null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    with database.force_rollback():
        async with database:
            yield


async def test_bulk_create_another_tenant():
    await Product.using("mamas").query.bulk_create(
        [
            {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
            {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
        ]
    )
    products = await Product.query.all()
    assert len(products) == 2
    assert products[0].data == {"foo": 123}
    assert products[0].value == 123.456
    assert products[0].status == StatusEnum.RELEASED
    assert products[1].data == {"foo": 456}
    assert products[1].value == 456.789
    assert products[1].status == StatusEnum.DRAFT
