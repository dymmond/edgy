from typing import Optional

import pytest
from pydantic import __version__

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=True)
models = edgy.Registry(database=database)


pytestmark = pytest.mark.anyio
pydantic_version = __version__[:3]

# TODO: disallow loading and check the crashes


class EdgyTenantBaseModel(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)

    class Meta:
        registry = models
        abstract = True


class Profle(edgy.Model):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    profile: Profle = edgy.ForeignKey(Profle)

    class Meta:
        registry = models


class Designation(EdgyTenantBaseModel):
    name: str = edgy.CharField(max_length=100)
    user: User = edgy.ForeignKey(User, null=True)

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


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_inner_select():
    designation = await Designation.query.create(name="admin")
    module = await AppModule.query.create(name="payroll")

    await Permission.query.create(designation=designation, module=module)

    query = await Permission.query.all()

    assert len(query) == 1

    query = await Permission.query.first()

    name = query.designation.name

    assert name == designation.name


async def test_inner_select_nested():
    profile = await Profle.query.create(name="super_admin")
    user = await User.query.create(name="user", profile=profile)
    designation = await Designation.query.create(name="admin", user=user)
    module = await AppModule.query.create(name="payroll")

    await Permission.query.create(designation=designation, module=module)

    query = await Permission.query.all()

    assert len(query) == 1

    query = await Permission.query.first()

    name = query.designation.name

    assert name == designation.name
    assert query.designation.user.name == user.name
    assert query.designation.user.profile.name == profile.name


async def test_raise_attribute_error_select():
    designation = await Designation.query.create(name="admin")
    module = await AppModule.query.create(name="payroll")

    await Permission.query.create(designation=designation, module=module)

    query = await Permission.query.all()

    assert len(query) == 1

    query = await Permission.query.first()

    with pytest.raises(AttributeError):
        query.designation.test  # noqa
