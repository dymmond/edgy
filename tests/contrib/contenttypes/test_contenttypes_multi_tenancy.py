import pytest

from edgy import Registry
from edgy.contrib.multi_tenancy import TenantModel
from edgy.contrib.multi_tenancy.models import TenantMixin
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, drop_database=True, use_existing=False)


models = Registry(database=database, with_content_type=True)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


class Tenant(TenantMixin):
    class Meta:
        registry = models


class User(TenantModel):
    id: int = fields.IntegerField(primary_key=True)
    name: str = fields.CharField(max_length=255)

    class Meta:
        registry = models
        is_tenant = True
        register_default = False


class Product(TenantModel):
    id: int = fields.IntegerField(primary_key=True)
    name: str = fields.CharField(max_length=255)
    user: User = fields.ForeignKey(User, null=True)

    class Meta:
        registry = models
        is_tenant = True
        register_default = False


async def test_tenant_model_metaclass_tenant_models():
    assert "User" not in models.models
    assert "User" in models.tenant_models
    assert Product.__name__ in Product.meta.registry.tenant_models
    assert "ContentType" not in Product.meta.registry.tenant_models


async def test_model_crud():
    edgy = await Tenant.query.create(
        schema_name="edgy", domain_url="https://edgy.tarsild.io", tenant_name="edgy"
    )

    users = await User.query.using(schema=edgy.schema_name).all()
    assert users == []

    user = await User.query.using(schema=edgy.schema_name).create(name="Test")
    users = await User.query.using(schema=edgy.schema_name).all()
    assert user.name == "Test"
    assert user.pk is not None
    assert users == [user]

    lookup = await User.query.using(schema=edgy.schema_name).get()
    assert lookup == user

    await user.update(name="Jane")
    users = await User.query.using(schema=edgy.schema_name).all()
    assert user.name == "Jane"
    assert user.pk is not None
    assert users == [user]

    await user.delete()
    users = await User.query.using(schema=edgy.schema_name).all()
    assert users == []


async def _test_can_have_multiple_tenants_with_different_records():
    edgy = await Tenant.query.create(
        schema_name="edgy", domain_url="https://edgy.tarsild.io", tenant_name="edgy"
    )
    saffier = await Tenant.query.create(
        schema_name="saffier", domain_url="https://saffier.tarsild.io", tenant_name="saffier"
    )

    # Create a user for edgy
    user_edgy = await User.query.using(schema=edgy.schema_name).create(name="Edgy")

    # Create products for user_edgy
    for i in range(5):
        await Product.query.using(schema=edgy.schema_name).create(
            name=f"product-{i}", user=user_edgy
        )

    # Create a user for saffier
    user_saffier = await User.query.using(schema=saffier.schema_name).create(name="Saffier")

    # Create products for user_saffier
    for i in range(25):
        await Product.query.using(schema=saffier.schema_name).create(
            name=f"product-{i}", user=user_saffier
        )

    # Create top level users
    for name in range(10):
        await User.query.using(schema=saffier.schema_name).create(name=f"user-{name}")
        await User.query.using(schema=edgy.schema_name).create(name=f"user-{name}")
        await User.query.create(name=f"user-{name}")

    # Check the totals
    users_edgy = await User.query.using(schema=edgy.schema_name).all()
    assert len(users_edgy) == 11

    users_saffier = await User.query.using(schema=saffier.schema_name).all()
    assert len(users_saffier) == 11
    assert await models.content_type.query.filter(name="User").count() == 32
