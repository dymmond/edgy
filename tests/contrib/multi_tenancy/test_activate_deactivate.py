from datetime import datetime

import pytest
from tests.settings import DATABASE_URL

from edgy.contrib.multi_tenancy import TenantModel, TenantRegistry
from edgy.contrib.multi_tenancy.models import TenantMixin
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
models = TenantRegistry(database=database)

pytestmark = pytest.mark.anyio


def time():
    return datetime.now().time()


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    try:
        await models.create_all()
        yield
        await models.drop_all()
    except Exception as e:
        pytest.skip(f"Error: {str(e)}")


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def drop_schemas(name):
    await models.schema.drop_schema(name, if_exists=True)


class Tenant(TenantMixin):
    class Meta:
        registry = models


class User(TenantModel):
    id: int = fields.IntegerField(primary_key=True)
    name: str = fields.CharField(max_length=255)

    class Meta:
        registry = models
        is_tenant = True


class Product(TenantModel):
    id: int = fields.IntegerField(primary_key=True)
    name: str = fields.CharField(max_length=255)
    user: User = fields.ForeignKey(User, null=True)

    class Meta:
        registry = models
        is_tenant = True


async def test_activate_and_deactivate_tenant():
    edgy = await Tenant.query.create(
        schema_name="edgy", domain_url="https://edgy.tarsild.io", tenant_name="edgy"
    )

    edgy.activate()

    # Create a user for edgy
    user = await User.query.create(name="Edgy")

    for i in range(25):
        await Product.query.create(name=f"product-{i}", user=user)

    total_users = await User.query.all()
    assert len(total_users) == 1

    total_products = await Product.query.all()
    assert len(total_products) == 25

    edgy.deactivate()

    total_users = await User.query.all()
    assert len(total_users) == 0

    total_products = await Product.query.all()
    assert len(total_products) == 0
