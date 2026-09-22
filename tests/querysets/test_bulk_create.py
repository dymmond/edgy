import decimal
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

import pytest

import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


def time():
    return datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class Product(edgy.StrictModel):
    id: int = fields.IntegerField(primary_key=True, autoincrement=True)
    uuid: UUID = fields.UUIDField(null=True)
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


class FooReflected(edgy.Model):
    foo = edgy.IntegerField()

    class Meta:
        registry = models


class Album(edgy.Model):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Track(edgy.Model):
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE)
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

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


async def test_empty_bulk_create():
    await Product.query.bulk_create([])


async def test_bulk_create():
    products = await Product.query.bulk_create(
        [
            {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
            {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
        ]
    )
    assert len(products) == 2
    assert products[0].data == {"foo": 123}
    assert products[0].value == 123.456
    assert products[0].status == StatusEnum.RELEASED
    assert not products[0].can_load
    assert products[1].data == {"foo": 456}
    assert products[1].value == 456.789
    assert products[1].status == StatusEnum.DRAFT
    assert not products[1].can_load


async def test_bulk_create_ignore_conflicts():
    await Product.query.bulk_create(
        [
            {"id": 40, "value": 123.456, "status": StatusEnum.RELEASED},
            {"id": 41, "value": 456.789, "status": StatusEnum.DRAFT},
        ],
        ignore_conflicts=True,
    )

    await Product.query.bulk_create(
        [
            {"id": 41, "value": 1, "status": StatusEnum.RELEASED},
            {"id": 42, "value": 456.789, "status": StatusEnum.DRAFT},
        ],
        ignore_conflicts=True,
    )
    products = await Product.query.order_by("id")
    assert len(products) == 3
    assert products[0].id == 40
    assert products[0].value == 123.456
    assert products[1].id == 41
    assert products[1].value == 456.789
    assert products[2].id == 42


async def test_bulk_create_reflected():
    # we delete "id" as field to simulate reflection models
    FooReflected.meta.fields.pop("id", None)
    results = await FooReflected.query.bulk_create(
        [
            {"foo": 2},
            {"foo": 3, "id": 100},
        ]
    )
    assert results[0].foo == 2
    assert not results[0].can_load
    assert not results[1].can_load
    assert results[1].foo == 3
    assert results[1].id != 100


async def test_bulk_create_reflected_ignore():
    # we delete "id" as field to simulate reflection models
    FooReflected.meta.fields.pop("id", None)
    results = await FooReflected.query.bulk_create(
        [
            {"foo": 2},
            {"foo": 3, "id": 100},
        ],
        ignore_conflicts=True,
    )
    assert results[0].foo == 2
    assert results[0].can_load
    assert results[1].can_load
    assert results[1].foo == 3
    assert results[1].id != 100


async def test_bulk_create_resolve_through():
    results = await Track.query.update_embed_parent(("album", "track_used")).bulk_create(
        [
            {"album": Album(name="test"), "position": 1, "title": "foo"},
            {"id": 100, "album": Album(name="foo"), "position": 2, "title": "fighters"},
        ],
        resolve_embed=True,
    )
    assert results[0].get_real_class() is Album
    assert results[0].id
    assert results[0].track_used.title == "foo"
    assert results[1].get_real_class() is Album
    assert results[1].id
    assert results[1].track_used.title == "fighters"


async def test_bulk_create_dedupe():
    results = await Product.query.bulk_create(
        [
            {"id": 40, "value": 123.456, "status": StatusEnum.RELEASED},
            {"id": 40, "value": 456.789, "status": StatusEnum.DRAFT},
        ]
    )
    assert results[1] is results[0]
    assert await Product.query.count() == 1


async def test_bulk_create_dedupe_ignore():
    results = await Product.query.bulk_create(
        [
            {"id": 40, "value": 123.456, "status": StatusEnum.RELEASED},
            {"id": 40, "value": 456.789, "status": StatusEnum.DRAFT},
        ],
        ignore_conflicts=True,
    )
    assert results[1] is None
    assert await Product.query.count() == 1
