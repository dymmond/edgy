from typing import Optional

import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


pytestmark = pytest.mark.anyio


class EdgyTenantBaseModel(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)

    class Meta:
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
    module: Optional[AppModule] = edgy.ForeignKey(AppModule, null=True)
    designation: Optional[Designation] = edgy.ForeignKey("Designation", null=True)
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
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models:
        yield


async def test_select_related():
    designation = await Designation.query.create(name="admin")
    module = await AppModule.query.create(name="payroll")

    permission = await Permission.query.create(designation=designation, module=module)

    query = await Permission.query.all()

    assert len(query) == 1

    query = await Permission.query.select_related("designation", "module").all()

    assert len(query) == 1
    assert query[0].pk == permission.pk

    assert query[0].designation.model_dump() == {"id": 1, "name": "admin"}
    assert query[0].module.model_dump() == {"id": 1, "name": "payroll"}


async def test_select_related_without_relation():
    permission = await Permission.query.create()
    permission2 = await Permission.query.create()

    query = await Permission.query.all()

    assert len(query) == 2

    query = await Permission.query.select_related("designation", "module").all()

    assert len(query) == 2
    assert query[0].pk == permission.pk
    assert query[1].pk == permission2.pk
