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


async def test_empty_bulk_get_or_create():
    query = Product.query.all()
    await query
    assert query._cache_count == 0
    await query.bulk_get_or_create([])
    assert query._cache_count == 0


async def test_bulk_bulk_get_or_create():
    products_with_created = await Product.query.bulk_get_or_create(
        [
            {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
            {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
        ]
    )
    assert len(products_with_created) == 2
    assert products_with_created[0][1]
    assert products_with_created[0][0].data == {"foo": 123}
    assert products_with_created[0][0].value == 123.456
    assert products_with_created[0][0].status == StatusEnum.RELEASED
    assert products_with_created[1][0].data == {"foo": 456}
    assert products_with_created[1][0].value == 456.789
    assert products_with_created[1][0].status == StatusEnum.DRAFT
    assert products_with_created[1][1]

    # retry
    products = await Product.query.all()
    assert len(products) == 2
    assert products[0].id
    assert products[0].data == {"foo": 123}
    assert products[0].value == 123.456
    assert products[0].status == StatusEnum.RELEASED
    assert products[1].id
    assert products[1].data == {"foo": 456}
    assert products[1].value == 456.789
    assert products[1].status == StatusEnum.DRAFT


async def test_bulk_bulk_get_or_create_resolve_embed():
    albums = await Track.query.update_embed_parent(("album", "embedded")).bulk_get_or_create(
        [
            {"album": Album(name="foo"), "position": 1, "title": "foo"},
            {"album": Album(name="fighters"), "position": 2, "title": "fighters"},
        ],
        resolve_embed=True,
    )
    assert albums[0][0].get_real_class() is Album
    assert albums[0][0].id
    assert albums[1][0].get_real_class() is Album
    assert albums[1][0].id
    tracks = await Track.query.all()
    assert tracks[0].album.pk == albums[0][0].pk
    assert tracks[1].album.pk == albums[1][0].pk


async def test_bulk_get_or_create_no_duplicates():
    results = await Product.query.bulk_get_or_create(
        [
            {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
            {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
        ]
    )
    assert results[0][1]
    assert results[1][1]
    assert await Product.query.count() == 2

    results = await Product.query.bulk_get_or_create(
        [
            {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
            {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
        ],
        unique_fields=["value", "status"],
    )
    assert not results[0][1]
    assert not results[1][1]

    products = await Product.query.all()
    assert len(products) == 2
    assert products[0].data == {"foo": 123}
    assert products[0].value == 123.456
    assert products[0].status == StatusEnum.RELEASED
    assert products[1].data == {"foo": 456}
    assert products[1].value == 456.789
    assert products[1].status == StatusEnum.DRAFT


async def test_bulk_get_or_create_no_duplicates_filter_by_dict():
    await Product.query.bulk_get_or_create(
        [
            {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
            {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
        ]
    )

    await Product.query.bulk_get_or_create(
        [
            {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
            {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
        ],
        unique_fields=["data"],
    )

    products = await Product.query.all()
    assert len(products) == 2
    assert products[0].data == {"foo": 123}
    assert products[0].value == 123.456
    assert products[0].status == StatusEnum.RELEASED
    assert products[1].data == {"foo": 456}
    assert products[1].value == 456.789
    assert products[1].status == StatusEnum.DRAFT
