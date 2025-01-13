import pytest

from edgy import Database, Registry
from edgy.contrib.multi_tenancy import TenantModel
from edgy.contrib.multi_tenancy.models import TenantMixin
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, use_existing=False)
models = Registry(database=Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    async with models.database:
        yield


class Tenant(TenantMixin):
    class Meta:
        registry = models


class User(TenantModel):
    id: int = fields.IntegerField(primary_key=True, autoincrement=True)
    name: str = fields.CharField(max_length=255)

    class Meta:
        registry = models
        is_tenant = True


class Product(TenantModel):
    id: int = fields.IntegerField(primary_key=True, autoincrement=True)
    name: str = fields.CharField(max_length=255)
    user: User = fields.ForeignKey(User, null=True)

    class Meta:
        registry = models
        is_tenant = True


class Cart(TenantModel):
    products = fields.ManyToMany(Product)

    class Meta:
        registry = models
        is_tenant = True


@pytest.mark.parametrize("use_copy", ["false", "instant", "after"])
async def test_schema_with_using_in_different_place(use_copy):
    if use_copy == "instant":
        copied = models.__copy__()
        NewTenant = copied.get_model("Tenant")
        NewProduct = copied.get_model("Product")
        NewCart = copied.get_model("Cart")
    else:
        NewTenant = Tenant
        NewProduct = Product
        NewCart = Cart
    tenant = await NewTenant.query.create(
        schema_name="edgy", domain_url="https://edgy.dymmond.com", tenant_name="edgy"
    )
    if use_copy == "after":
        copied = models.__copy__()
        NewTenant = copied.get_model("Tenant")
        NewProduct = copied.get_model("Product")
        NewCart = copied.get_model("Cart")
    cart = await NewCart.query.using(schema=tenant.schema_name).create()
    assert cart.__using_schema__ == tenant.schema_name
    for i in range(5):
        product = await NewProduct.query.using(schema=tenant.schema_name).create(
            name=f"product-{i}"
        )
        if i % 2 == 0:
            product_through = cart.products.through(cart=cart, product=product)
            product_through.__using_schema__ = tenant.schema_name
            assert await cart.products.add(product_through)
        else:
            assert await cart.products.add(product)

    total = await NewProduct.query.filter().using(schema=tenant.schema_name).all()

    assert len(total) == 5

    total = await cart.products.filter().using(schema=tenant.schema_name).all()

    assert len(total) == 5

    total = await NewProduct.query.all()

    assert len(total) == 0

    for i in range(15):
        await NewProduct.query.create(name=f"product-{i}")

    total = await NewProduct.query.all()

    assert len(total) == 15

    total = await NewProduct.query.filter().using(schema=tenant.schema_name).all()

    assert len(total) == 5


async def test_can_have_multiple_tenants_with_different_records_with_using():
    edgy = await Tenant.query.create(
        schema_name="edgy", domain_url="https://edgy.dymmond.com", tenant_name="edgy"
    )
    saffier = await Tenant.query.create(
        schema_name="saffier", domain_url="https://saffier.tarsild.io", tenant_name="saffier"
    )

    # Create a user for edgy
    user_edgy = await User.query.only().using(schema=edgy.schema_name).create(name="Edgy")

    # Create products for user_edgy
    for i in range(5):
        await (
            Product.query.defer()
            .using(schema=edgy.schema_name)
            .create(name=f"product-{i}", user=user_edgy)
        )

    # Create a user for saffier
    user_saffier = (
        await User.query.group_by().using(schema=saffier.schema_name).create(name="Saffier")
    )

    # Create products for user_saffier
    for i in range(25):
        await (
            Product.query.exclude()
            .using(schema=saffier.schema_name)
            .create(name=f"product-{i}", user=user_saffier)
        )

    # Create top level users
    for name in range(10):
        await User.query.filter().using(schema=saffier.schema_name).create(name=f"user-{name}")
        await User.query.filter().using(schema=edgy.schema_name).create(name=f"user-{name}")
        await User.query.distinct().create(name=f"user-{name}")

    # Check the totals
    top_level_users = await User.query.all()
    assert len(top_level_users) == 10

    users_edgy = await User.query.using(schema=edgy.schema_name).all()
    assert len(users_edgy) == 11

    users_saffier = await User.query.using(schema=saffier.schema_name).all()
    assert len(users_saffier) == 11
