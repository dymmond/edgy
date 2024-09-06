import pytest
from pydantic import __version__

from edgy import fields
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
    try:
        await models.create_all()
        yield
        await models.drop_all()
    except Exception:
        pytest.skip("No database available")


@pytest.fixture(autouse=True)
async def rollback_transactions():
    with database.force_rollback():
        async with database:
            yield


async def test_queries():
    tenant = await Tenant.query.create(schema_name="edgy", tenant_name="edgy")

    # Create a product with a user
    user = await User.query.using(tenant.schema_name).create(name="user")
    product = await Product.query.using(tenant.schema_name).create(name="product-1", user=user)

    # Query tenants
    users = await User.query.using(tenant.schema_name).all()
    assert len(users) == 1

    products = await Product.query.using(tenant.schema_name).all()
    assert len(products) == 1

    # Query related
    prod = await Product.query.using(tenant.schema_name).filter(user__name__icontains="u").get()

    assert prod.id == product.id
    assert prod.table.schema == tenant.schema_name
