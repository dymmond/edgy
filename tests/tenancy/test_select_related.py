import pytest

from edgy import Registry, fields
from edgy.contrib.multi_tenancy import TenantModel
from edgy.contrib.multi_tenancy.models import TenantMixin
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = Registry(database=database)


pytestmark = pytest.mark.anyio


class Tenant(TenantMixin):
    class Meta:
        registry = models


class Base(TenantModel):
    class Meta:
        abstract = True
        registry = models


class User(TenantModel):
    name: str = fields.CharField(max_length=255)

    class Meta:
        registry = models
        is_tenant = True


class Product(TenantModel):
    name: str = fields.CharField(max_length=255)
    user: User = fields.ForeignKey(User, null=True, related_name="products")

    class Meta:
        registry = models
        is_tenant = True


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback():
        async with models:
            yield


async def test_select_related_tenant():
    tenant = await Tenant.query.create(schema_name="edgy", tenant_name="edgy")

    # Create a product with a user
    user = await User.query.using(schema=tenant.schema_name).create(name="user")
    product = await Product.query.using(schema=tenant.schema_name).create(
        name="product-1", user=user
    )

    prod = await Product.query.using(schema=tenant.schema_name).select_related("user").get(pk=1)

    assert prod.pk == product.pk
    assert prod.user.name == "user"
