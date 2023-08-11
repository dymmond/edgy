import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.contrib.multi_tenancy.exceptions import ModelSchemaError
from edgy.contrib.multi_tenancy.models import DomainMixin, TenantMixin
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    try:
        await models.create_all()
        yield
        await models.drop_all()
    except Exception:
        pytest.skip("No database available")


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


class Tenant(TenantMixin):
    class Meta:
        registry = models


class Domain(DomainMixin):
    class Meta:
        registry = models


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
