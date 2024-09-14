import copy
import decimal
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict
from uuid import UUID

import pytest

import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_ALTERNATIVE_URL, DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
another_db = DatabaseTestClient(DATABASE_ALTERNATIVE_URL, use_existing=False)
models = edgy.Registry(database=database, extra={"another": another_db})


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
    price: decimal.Decimal = fields.DecimalField(max_digits=9, decimal_places=2, null=True)
    status: str = fields.ChoiceField(StatusEnum, default=StatusEnum.DRAFT)
    value: float = fields.FloatField(null=True)

    class Meta:
        registry = models


registry = copy.copy(models)
registry.database = another_db


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database, another_db:
        await models.create_all()
        registry.metadata = models.metadata
        await registry.create_all(False)
        yield
        if not database.drop:
            await models.drop_all()
        if not another_db.drop:
            await registry.drop_all()


async def test_bulk_create_another_db():
    await Product.query.using_with_db("another").bulk_create(
        [
            {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
            {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
        ]
    )

    products = await Product.query.all()

    assert len(products) == 0

    others = await Product.query.using_with_db("another").all()

    assert len(others) == 2


async def test_bulk_create_another_schema_and_db():
    await registry.schema.create_schema("foo", init_models=True, if_not_exists=True)
    try:
        await Product.query.using_with_db("another", "foo").bulk_create(
            [
                {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
                {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
            ]
        )

        products = await Product.query.all()

        assert len(products) == 0

        products = await Product.query.using_with_db("another").all()

        assert len(products) == 0

        others = await Product.query.using_with_db("another", "foo").all()

        assert len(others) == 2
    finally:
        await registry.schema.drop_schema("foo", cascade=True)
