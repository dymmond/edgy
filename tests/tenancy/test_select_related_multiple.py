from typing import Optional

import pytest
from pydantic import __version__

import edgy
from edgy.contrib.multi_tenancy import TenantModel, TenantRegistry
from edgy.contrib.multi_tenancy.models import TenantMixin
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = TenantRegistry(database=database)


pytestmark = pytest.mark.anyio
pydantic_version = __version__[:3]


class Tenant(TenantMixin):
    class Meta:
        registry = models


class EdgyTenantBaseModel(TenantModel):
    id: int = edgy.IntegerField(primary_key=True)

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
    async with database:
        await models.create_all()
        yield
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models.database:
        yield


async def test_select_related_tenant():
    tenant = await Tenant.query.create(schema_name="edgy", tenant_name="edgy")
    designation = await Designation.query.using(tenant.schema_name).create(name="admin")
    module = await AppModule.query.using(tenant.schema_name).create(name="payroll")

    permission = await Permission.query.using(tenant.schema_name).create(
        designation=designation, module=module
    )

    query = await Permission.query.all()

    assert len(query) == 0

    query = (
        await Permission.query.using(tenant.schema_name)
        .select_related(["designation", "module"])
        .all()
    )

    assert len(query) == 1
    assert query[0].pk == permission.pk

    assert query[0].designation.model_dump() == {"id": 1, "name": "admin"}
    assert query[0].module.model_dump() == {"id": 1, "name": "payroll"}
