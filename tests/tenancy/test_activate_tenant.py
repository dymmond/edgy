from typing import Optional

import pytest

import edgy
from edgy.contrib.multi_tenancy import TenantModel
from edgy.contrib.multi_tenancy.models import TenantMixin
from edgy.core.db.querysets.mixins import with_schema
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)


pytestmark = pytest.mark.anyio


class Tenant(TenantMixin):
    class Meta:
        registry = models


class EdgyTenantBaseModel(TenantModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)

    class Meta:
        is_tenant = True
        registry = models
        abstract = True


class Designation(EdgyTenantBaseModel):
    name: str = edgy.CharField(max_length=100)

    class Meta:
        tablename = "ut_designation"


class AppModule(EdgyTenantBaseModel):
    name: str = edgy.CharField(max_length=100)

    class Meta:
        tablename = "ut_module"


class Permission(EdgyTenantBaseModel):
    module: Optional[AppModule] = edgy.ForeignKey(AppModule)
    designation: Optional[Designation] = edgy.ForeignKey("Designation")
    can_read: bool = edgy.BooleanField(default=False)
    can_write: bool = edgy.BooleanField(default=False)
    can_update: bool = edgy.BooleanField(default=False)
    can_delete: bool = edgy.BooleanField(default=False)
    can_approve: bool = edgy.BooleanField(default=False)

    class Meta:
        tablename = "ut_permission"


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


async def test_activate_related_tenant():
    tenant = await Tenant.query.create(schema_name="edgy", tenant_name="edgy")

    # Activate the schema and query always the tenant set
    with with_schema(tenant.schema_name):
        designation = await Designation.query.create(name="admin")
        module = await AppModule.query.create(name="payroll")

        permission = await Permission.query.create(designation=designation, module=module)

        query = await Permission.query.all()

        assert len(query) == 1
        assert query[0].pk == permission.pk

    query = await Permission.query.all()

    assert len(query) == 0

    # Even if the with_schema is enabled
    # The use of `using` takes precedence
    query = (
        await Permission.query.using(schema=tenant.schema_name).select_related("designation").all()
    )

    assert len(query) == 1
    assert query[0].pk == permission.pk
