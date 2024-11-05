from __future__ import annotations

import pydantic
import pytest

import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models:
        yield


class Computer(edgy.StrictModel):
    url = fields.URLField(null=True)

    class Meta:
        registry = models


async def test_ip_field_full_str():
    computer = Computer(url="http://foo.example.com")

    assert isinstance(computer.url, str)
    assert computer.url == "http://foo.example.com/"


async def test_can_use_ip_field_full_str():
    computer = await Computer.query.create(url="http://foo.example.com")

    assert isinstance(computer.url, str)
    assert computer.url == "http://foo.example.com/"


async def test_can_use_url_field_none():
    computer = await Computer.query.create()

    assert computer.url is None


async def test_raise_validation_error():
    with pytest.raises(pydantic.ValidationError):  # noqa
        await Computer.query.create(url="127.0.0.1")
