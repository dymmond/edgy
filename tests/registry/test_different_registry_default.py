from enum import Enum

import pytest

import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database, schema="another")


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class Product(edgy.Model):
    id: int = fields.IntegerField(primary_key=True, autoincrement=True)
    name: str = fields.CharField(max_length=255)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_bulk_create():
    await Product.query.bulk_create(
        [
            {"name": "product-1"},
            {"name": "product-2"},
        ]
    )

    total = await Product.query.all()

    assert len(total) == 2
    assert Product.table.schema == models.db_schema
