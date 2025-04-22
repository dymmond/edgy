from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address

import pydantic
import pytest
import sqlalchemy

import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


class Computer(edgy.StrictModel):
    ip1: IPv4Address | IPv6Address = fields.IPAddressField(null=True)
    ip2: IPv4Address | IPv6Address = fields.IPAddressField(null=False)

    class Meta:
        registry = models


async def test_column_type():
    assert isinstance(
        Computer.table.c.ip1.type.impl,
        sqlalchemy.String,
    )
    assert isinstance(
        Computer.table.c.ip1.type.load_dialect_impl(database.engine.dialect),
        sqlalchemy.dialects.postgresql.INET,
    )


async def test_can_use_ip_field_full_str():
    computer = await Computer.query.create(ip1="127.0.0.1", ip2=IPv6Address("::1"))

    assert isinstance(computer.ip1, IPv4Address)
    assert computer.ip1 == IPv4Address("127.0.0.1")
    assert isinstance(computer.ip2, IPv6Address)
    assert computer.ip2 == IPv6Address("::1")


async def test_can_use_ip_field_half_str():
    computer = await Computer.query.create(ip2=IPv6Address("::1"))

    assert computer.ip1 is None
    assert computer.ip2 == IPv6Address("::1")


async def test_raise_validation_error_none():
    with pytest.raises(pydantic.ValidationError):  # noqa
        await Computer.query.create(ip1="127.0.0.1")
