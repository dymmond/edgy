from uuid import UUID

import pytest
from esmerald import Esmerald

import edgy
from edgy import Instance, Registry
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
    id: int = fields.IntegerField(primary_key=True, autoincrement=True)
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

    with edgy.monkay.with_instance(Instance(app=app, registry=models)):
        registry = edgy.get_migration_prepared_registry()
        assert len(registry.metadata_by_name[None].tables.keys()) == 2


async def test_migrate_objs_main_only_after_copy():
    tenant = await Tenant.query.create(
        schema_name="migrate_edgy",
        domain_url="https://edgy.dymmond.com",
        tenant_name="migrate_edgy",
    )

    assert tenant.schema_name == "migrate_edgy"
    assert tenant.tenant_name == "migrate_edgy"

    registry = edgy.get_migration_prepared_registry(models.__copy__())
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

    with (
        edgy.monkay.with_instance(Instance(app=app, registry=models)),
        edgy.monkay.with_settings(edgy.monkay.settings.model_copy(update={"multi_schema": True})),
    ):
        registry = edgy.get_migration_prepared_registry()

        assert set(registry.metadata_by_name[None].tables.keys()) == {
            "tenants",
            "migrate_edgy.products",
            "products",
        }


async def test_migrate_objs_all_after_copy():
    tenant = await Tenant.query.create(
        schema_name="migrate_edgy",
        domain_url="https://edgy.dymmond.com",
        tenant_name="migrate_edgy",
    )

    assert tenant.schema_name == "migrate_edgy"
    assert tenant.tenant_name == "migrate_edgy"

    with (
        edgy.monkay.with_instance(Instance(registry=models.__copy__())),
        edgy.monkay.with_settings(edgy.monkay.settings.model_copy(update={"multi_schema": True})),
    ):
        registry = edgy.get_migration_prepared_registry()

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

    with (
        edgy.monkay.set_instance(Instance(app=app, registry=models)),
        edgy.monkay.with_settings(
            edgy.monkay.settings.model_copy(update={"multi_schema": "saffier"})
        ),
    ):
        registry = edgy.get_migration_prepared_registry()

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

    # here test set_instance
    edgy.monkay.set_instance(Instance(app=app, registry=models))
    with edgy.monkay.with_settings(
        edgy.monkay.settings.model_copy(update={"multi_schema": "saffier|^$"})
    ):
        registry = edgy.get_migration_prepared_registry()
        assert set(registry.metadata_by_name[None].tables.keys()) == {
            "saffier.products",
            "products",
            "tenants",
        }
    edgy.monkay.set_instance(None)
