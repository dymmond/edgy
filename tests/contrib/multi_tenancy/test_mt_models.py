import decimal
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict
from uuid import UUID

import pytest

from edgy import Database, Registry
from edgy.contrib.multi_tenancy import TenantModel
from edgy.contrib.multi_tenancy.models import TenantMixin
from edgy.core.db import fields
from edgy.exceptions import ModelSchemaError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = Registry(database=Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


def time():
    return datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    async with models.database:
        yield


class Tenant(TenantMixin):
    class Meta:
        registry = models


class Product(TenantModel):
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
        is_tenant = True


async def test_create_a_tenant_schema():
    tenant = await Tenant.query.create(
        schema_name="edgy", domain_url="https://edgy.dymmond.com", tenant_name="edgy"
    )

    assert tenant.schema_name == "edgy"
    assert tenant.tenant_name == "edgy"


async def test_raises_ModelSchemaError_on_public_schema():
    with pytest.raises(ModelSchemaError) as raised:
        await Tenant.query.create(
            schema_name="public", domain_url="https://edgy.dymmond.com", tenant_name="edgy"
        )

    assert (
        raised.value.args[0]
        == "Can't update tenant outside it's own schema or the public schema. Current schema is 'public'"
    )
