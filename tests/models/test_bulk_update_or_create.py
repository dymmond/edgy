import decimal
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

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


async def test_empty_bulk_update_or_create():
    await Product.query.bulk_update_or_create([])


async def test_bulk_update_or_create():
    products_with_created = await Product.query.bulk_update_or_create(
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
    assert products_with_created[1][1]
    assert products_with_created[1][0].data == {"foo": 456}
    assert products_with_created[1][0].value == 456.789
    assert products_with_created[1][0].status == StatusEnum.DRAFT


async def test_bulk_update_or_create_update():
    products_with_created = await Product.query.bulk_update_or_create(
        [
            {
                "data": {"foo": 123},
                "value": 123.456,
                "status": StatusEnum.RELEASED,
                "description": "abc",
            },
            {
                "data": {"foo": 456},
                "value": 456.789,
                "status": StatusEnum.DRAFT,
                "description": "abc",
            },
        ]
    )
    assert len(products_with_created) == 2
    assert products_with_created[0][0].data == {"foo": 123}
    assert products_with_created[0][1]
    assert products_with_created[1][0].data == {"foo": 456}
    assert products_with_created[1][1]

    products_with_created = await Product.query.bulk_update_or_create(
        [
            {
                "data": {"foo": 111},
                "value": 123.456,
                "status": StatusEnum.RELEASED,
                "description": "wrong",
            },
            {
                "data": {"foo": 234},
                "value": 456.789,
                "status": StatusEnum.DRAFT,
                "description": "wrong",
            },
        ],
        unique_fields=["value", "status"],
        update_fields=["data"],
    )

    assert len(products_with_created) == 2
    assert not products_with_created[0][1]
    assert products_with_created[0][0].data == {"foo": 111}
    assert products_with_created[0][0].value == 123.456
    assert products_with_created[0][0].status == StatusEnum.RELEASED
    assert products_with_created[0][0].description == "abc"
    assert not products_with_created[1][1]
    assert products_with_created[1][0].data == {"foo": 234}
    assert products_with_created[1][0].value == 456.789
    assert products_with_created[1][0].status == StatusEnum.DRAFT
    assert products_with_created[1][0].description == "abc"

    products = await Product.query.all()
    assert len(products) == 2
    assert products[0].data == {"foo": 111}
    assert products[0].value == 123.456
    assert products[0].status == StatusEnum.RELEASED
    assert products[0].description == "abc"
    assert products[1].data == {"foo": 234}
    assert products[1].value == 456.789
    assert products[1].status == StatusEnum.DRAFT
    assert products[1].description == "abc"


async def test_bulk_update_or_create_no_duplicates_filter_by_dict():
    await Product.query.bulk_update_or_create(
        [
            {"data": {"foo": 123}, "value": 123.456, "status": StatusEnum.RELEASED},
            {"data": {"foo": 456}, "value": 456.789, "status": StatusEnum.DRAFT},
        ]
    )

    await Product.query.bulk_update_or_create(
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


async def test_bulk_bulk_update_or_create_resolve_embed():
    album = Album(name="foo")
    albums = await Track.query.update_embed_parent(("album", "embedded")).bulk_update_or_create(
        [
            {"album": album, "position": 1, "title": "foo"},
            {"album": album, "position": 2, "title": "fighters"},
        ],
        resolve_embed=True,
    )
    assert albums[0][0].get_real_class() is Album
    assert albums[0][0].embedded.get_real_class() is Track
    assert albums[0][0].id
    assert albums[1][0].get_real_class() is Album
    assert albums[1][0].embedded.get_real_class() is Track
    assert albums[1][0].id
    tracks = await Track.query.all()
    assert tracks[0].album.pk == albums[0][0].pk
    assert tracks[1].album.pk == albums[1][0].pk

    tracks[0].title = "boo"
    tracks[1].title = "zoo"
    albums = await Track.query.update_embed_parent(("album", "embedded")).bulk_update_or_create(
        tracks,
        resolve_embed=True,
    )
    assert albums[0][0].embedded.title == "boo"
    assert albums[1][0].embedded.title == "zoo"


async def test_bulk_bulk_update_or_create_fail():
    with pytest.raises(ValueError):
        await Track.query.update_embed_parent(("album", "embedded")).bulk_update_or_create(
            [
                {"position": 1, "title": "foo"},
                {"album": Album(name="fighters"), "position": 2, "title": "fighters"},
            ],
            resolve_embed=True,
        )


async def test_bulk_update_or_create_create_new():
    await Album.query.bulk_update_or_create([{"name": "foo"}, {"name": "boo"}])
    assert await Album.query.count() == 2
    await Album.query.bulk_update_or_create([{"name": "foo"}, {"name": "boo"}])
    assert await Album.query.count() == 4


async def test_bulk_update_or_create_existing_pk():
    await Album.query.bulk_update_or_create([{"name": "foo"}, {"name": "boo"}])
    albums = await Album.query.all()
    assert len(albums) == 2
    await Album.query.bulk_update_or_create(albums)
    assert await Album.query.count() == 2


async def test_bulk_update_or_create_existing_unique():
    await Album.query.bulk_update_or_create(
        [{"name": "foo"}, {"name": "boo"}], unique_fields=["name"]
    )
    assert await Album.query.count() == 2
    await Album.query.bulk_update_or_create(
        [{"name": "foo"}, {"name": "boo"}], unique_fields=["name"]
    )
    assert await Album.query.count() == 2


async def test_bulk_update_or_create_unsuitable_unique():
    # uuid is here unique but not part of unique_fields
    products1 = await Product.query.bulk_create(
        [
            {"uuid": uuid4(), "status": StatusEnum.RELEASED},
            {"uuid": uuid4(), "status": StatusEnum.DRAFT},
            {"uuid": uuid4(), "status": StatusEnum.DRAFT},
        ],
    )
    assert len(products1) == 3
    products = await Product.query.bulk_update_or_create(
        [
            {"uuid": products1[0].uuid, "status": StatusEnum.RELEASED},
            {"uuid": products1[0].uuid, "status": StatusEnum.DRAFT},
            {"uuid": products1[0].uuid, "status": StatusEnum.DRAFT},
        ],
    )
    assert len(products) == 3
    assert products[0][0] is None
    products = await Product.query.all()
    assert len(products) == 3
    products = await Product.query.bulk_update_or_create(
        [
            {"uuid": products1[0].uuid, "status": StatusEnum.RELEASED},
            {"uuid": products1[0].uuid, "status": StatusEnum.DRAFT},
            {"uuid": products1[0].uuid, "status": StatusEnum.DRAFT},
        ],
        unique_fields=["id"],
    )
    assert len(products) == 3
    assert products[0][0] is None
    products = await Product.query.all()
    assert len(products) == 3
