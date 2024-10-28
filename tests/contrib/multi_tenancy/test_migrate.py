from uuid import UUID

import pytest
from esmerald import Esmerald

from edgy import Migrate, Registry
from edgy.contrib.multi_tenancy import TenantModel
from edgy.contrib.multi_tenancy.models import TenantMixin
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

# because we manipulate Metadata drop_all doesn't work reliable
database = DatabaseTestClient(DATABASE_URL, drop_database=True)
models = Registry(database=database)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with models:
        await models.create_all()
        yield


class Tenant(TenantMixin):
    class Meta:
        registry = models


class Product(TenantModel):
    id: int = fields.IntegerField(primary_key=True)
    uuid: UUID = fields.UUIDField(null=True)

    class Meta:
        registry = models
        is_tenant = True


async def test_migrate_objs_main_only():
    tenant = await Tenant.query.create(
        schema_name="migrate_edgy",
        domain_url="https://edgy.dymmond.com",
        tenant_name="migrate_edgy",
    )

    assert tenant.schema_name == "migrate_edgy"
    assert tenant.tenant_name == "migrate_edgy"

    app = Esmerald()

    migrate = Migrate(app=app, registry=models)
    registry = migrate.get_registry_copy()

    assert len(registry.metadata_by_name[None].tables.keys()) == 2


async def test_migrate_objs_all():
    tenant = await Tenant.query.create(
        schema_name="migrate_edgy",
        domain_url="https://edgy.dymmond.com",
        tenant_name="migrate_edgy",
    )

    assert tenant.schema_name == "migrate_edgy"
    assert tenant.tenant_name == "migrate_edgy"

    app = Esmerald()

    migrate = Migrate(app=app, registry=models, multi_schema=True)
    registry = migrate.get_registry_copy()

    assert set(registry.metadata_by_name[None].tables.keys()) == {
        "tenants",
        "migrate_edgy.products",
        "products",
    }


async def test_migrate_objs_namespace_only():
    tenant = await Tenant.query.create(
        schema_name="migrate_edgy",
        domain_url="https://edgy.dymmond.com",
        tenant_name="migrate_edgy",
    )
    await Tenant.query.create(
        schema_name="saffier", domain_url="https://saffier.dymmond.com", tenant_name="saffier"
    )

    assert tenant.schema_name == "migrate_edgy"
    assert tenant.tenant_name == "migrate_edgy"

    app = Esmerald()

    migrate = Migrate(app=app, registry=models, multi_schema="saffier")
    registry = migrate.get_registry_copy()

    assert set(registry.metadata_by_name[None].tables.keys()) == {"saffier.products"}


async def test_migrate_objs_few():
    tenant = await Tenant.query.create(
        schema_name="migrate_edgy",
        domain_url="https://edgy.dymmond.com",
        tenant_name="migrate_edgy",
    )
    await Tenant.query.create(
        schema_name="saffier", domain_url="https://saffier.dymmond.com", tenant_name="saffier"
    )

    assert tenant.schema_name == "migrate_edgy"
    assert tenant.tenant_name == "migrate_edgy"

    app = Esmerald()

    migrate = Migrate(app=app, registry=models, multi_schema="saffier|^$")
    registry = migrate.get_registry_copy()

    assert set(registry.metadata_by_name[None].tables.keys()) == {
        "saffier.products",
        "products",
        "tenants",
    }
