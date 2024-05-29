from datetime import date, datetime, timedelta
from enum import Enum

import pytest

import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL)
models = edgy.Registry(database=database)


def time():
    return datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class BaseModel(edgy.Model):
    class Meta:
        registry = models


class Product(BaseModel):
    id = fields.IntegerField(primary_key=True)
    uuid = fields.UUIDField(null=True)
    created = fields.DateTimeField(default=datetime.now)
    created_day = fields.DateField(default=date.today)
    created_time = fields.TimeField(default=time)
    created_date = fields.DateField(auto_now_add=True)
    created_datetime = fields.DateTimeField(auto_now_add=True)
    updated_datetime = fields.DateTimeField(auto_now=True)
    updated_date = fields.DateField(auto_now=True)
    data = fields.JSONField(default={})
    description = fields.CharField(null=True, max_length=255)
    huge_number = fields.BigIntegerField(default=0)
    price = fields.DecimalField(max_digits=9, decimal_places=2, null=True)
    status = fields.ChoiceField(StatusEnum, default=StatusEnum.DRAFT)
    value = fields.FloatField(null=True)


class Album(BaseModel):
    name = edgy.CharField(max_length=100)


class Track(BaseModel):
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE)
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()


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


async def test_bulk_update():
    edgy.run_sync(
        Product.query.bulk_create(
            [
                {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
                {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
            ]
        )
    )
    products = edgy.run_sync(Product.query.all())
    assert len(products) == 2
    assert products[0].data == {"foo": 123}
    assert products[0].value == 123.456
    assert products[0].status == StatusEnum.RELEASED
    assert products[1].data == {"foo": 456}
    assert products[1].value == 456.789
    assert products[1].status == StatusEnum.DRAFT

    today_date = date.today() + timedelta(days=3)

    products = edgy.run_sync(Product.query.all())
    products[0].created_day = today_date
    products[1].created_day = today_date
    products[0].status = StatusEnum.DRAFT
    products[1].status = StatusEnum.RELEASED
    products[0].data = {"foo": "test"}
    products[1].data = {"foo": "test2"}
    products[0].value = 1
    products[1].value = 2

    edgy.run_sync(Product.query.bulk_update(products, fields=["created_day", "status", "data", "value"]))

    products = edgy.run_sync(Product.query.all())

    assert products[0].created_day == today_date
    assert products[1].created_day == today_date
    assert products[0].status == StatusEnum.DRAFT
    assert products[1].status == StatusEnum.RELEASED
    assert products[0].data == {"foo": "test"}
    assert products[1].data == {"foo": "test2"}
    assert products[0].value == 1
    assert products[1].value == 2


async def test_bulk_update_with_relation():
    album = edgy.run_sync(Album.query.create(name="foo"))
    album2 = edgy.run_sync(Album.query.create(name="fighters"))

    edgy.run_sync(
        Track.query.bulk_create(
            [
                {"name": "foo", "album": album, "position": 1, "title": "foo"},
                {"name": "bar", "album": album, "position": 2, "title": "fighters"},
            ]
        )
    )
    tracks = edgy.run_sync(Track.query.all())
    for track in tracks:
        track.album = album2

    edgy.run_sync(Track.query.bulk_update(tracks, fields=["album"]))
    tracks = edgy.run_sync(Track.query.all())
    assert tracks[0].album.pk == album2.pk
    assert tracks[1].album.pk == album2.pk
