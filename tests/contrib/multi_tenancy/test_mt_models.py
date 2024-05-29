import decimal
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict
from uuid import UUID

import pytest
from tests.settings import DATABASE_URL

from edgy.contrib.multi_tenancy import TenantModel, TenantRegistry
from edgy.contrib.multi_tenancy.models import TenantMixin
from edgy.core.db import fields
from edgy.exceptions import ModelSchemaError
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
models = TenantRegistry(database=database)

pytestmark = pytest.mark.anyio


def time():
    return datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    try:
        await models.create_all()
        yield
        await models.drop_all()
    except Exception as e:
        pytest.skip(f"Error: {str(e)}")


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
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
        schema_name="edgy", domain_url="https://edgy.tarsild.io", tenant_name="edgy"
    )

    assert tenant.schema_name == "edgy"
    assert tenant.tenant_name == "edgy"


async def test_raises_ModelSchemaError_on_public_schema():
    with pytest.raises(ModelSchemaError) as raised:
        await Tenant.query.create(
            schema_name="public", domain_url="https://edgy.tarsild.io", tenant_name="edgy"
        )

    assert (
        raised.value.args[0]
        == "Can't update tenant outside it's own schema or the public schema. Current schema is 'public'"
    )
