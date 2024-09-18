from typing import Any, AsyncGenerator, Coroutine, List

import pytest
from anyio import from_thread, sleep, to_thread
from esmerald import Esmerald, Gateway, Request, get
from esmerald.protocols.middleware import MiddlewareProtocol
from httpx import ASGITransport, AsyncClient
from lilya.types import ASGIApp, Receive, Scope, Send
from pydantic import __version__

from edgy import Registry
from edgy.contrib.multi_tenancy import TenantModel
from edgy.contrib.multi_tenancy.models import TenantMixin, TenantUserMixin
from edgy.core.db import fields, set_tenant
from edgy.exceptions import ObjectNotFound
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = Registry(database=database)


pytestmark = pytest.mark.anyio
pydantic_version = __version__[:3]


class Tenant(TenantMixin):
    class Meta:
        registry = models


class User(TenantModel):
    id: int = fields.IntegerField(primary_key=True)
    name: str = fields.CharField(max_length=255)
    email: str = fields.EmailField(max_length=255)

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


class TenantUser(TenantUserMixin):
    user = fields.ForeignKey("User", null=False, related_name="tenant_user_users_test")
    tenant = fields.ForeignKey("Tenant", null=False, related_name="tenant_users_tenant_test")

    class Meta:
        registry = models


class TenantMiddleware(MiddlewareProtocol):
    def __init__(self, app: "ASGIApp"):
        super().__init__(app)
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> Coroutine[Any, Any, None]:
        request = Request(scope=scope, receive=receive, send=send)

        tenant_header = request.headers.get("tenant", None)
        tenant_email = request.headers.get("email", None)

        try:
            _tenant = await Tenant.query.get(schema_name=tenant_header)
            user = await User.query.get(email=tenant_email)

            await TenantUser.query.get(tenant=_tenant, user=user)
            tenant = _tenant.schema_name
        except ObjectNotFound:
            tenant = None

        set_tenant(tenant)
        await self.app(scope, receive, send)


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    try:
        await models.create_all()
        yield
        await models.drop_all()
    except Exception:
        pytest.skip("No database available")


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


def blocking_function():
    from_thread.run(sleep, 0.1)


@get("/products")
async def get_products() -> List[Product]:
    products = await Product.query.all()
    return products


@pytest.fixture()
def app():
    app = Esmerald(
        routes=[Gateway(handler=get_products)],
        middleware=[TenantMiddleware],
        on_startup=[database.connect],
        on_shutdown=[database.disconnect],
    )
    return app


@pytest.fixture()
def another_app():
    app = Esmerald(
        routes=[Gateway("/no-tenant", handler=get_products)],
        on_startup=[database.connect],
        on_shutdown=[database.disconnect],
    )
    return app


@pytest.fixture()
async def async_cli(another_app) -> AsyncGenerator:
    async with AsyncClient(
        transport=ASGITransport(app=another_app), base_url="http://test"
    ) as acli:
        await to_thread.run_sync(blocking_function)
        yield acli


@pytest.fixture()
async def async_client(app) -> AsyncGenerator:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await to_thread.run_sync(blocking_function)
        yield ac


async def create_data():
    """
    Creates mock data
    """
    saffier = await User.query.create(name="saffier", email="saffier@esmerald.dev")
    user = await User.query.create(name="edgy", email="edgy@esmerald.dev")
    edgy_tenant = await Tenant.query.create(schema_name="edgy", tenant_name="edgy")

    edgy = await User.query.using(schema=edgy_tenant.schema_name).create(
        name="edgy", email="edgy@esmerald.dev"
    )

    await TenantUser.query.create(user=user, tenant=edgy_tenant)

    # Products for Edgy
    for i in range(10):
        await Product.query.using(schema=edgy_tenant.schema_name).create(
            name=f"Product-{i}", user=edgy
        )

    # Products for Saffier
    for i in range(25):
        await Product.query.create(name=f"Product-{i}", user=saffier)


async def test_user_query_tenant_data(async_client, async_cli):
    await create_data()

    # Test Edgy Response intercepted in the
    response_edgy = await async_client.get(
        "/products", headers={"tenant": "edgy", "email": "edgy@esmerald.dev"}
    )
    assert response_edgy.status_code == 200

    assert len(response_edgy.json()) == 10

    # Test Edgy Response intercepted in the
    response_saffier = await async_client.get("/products")
    assert response_saffier.status_code == 200

    assert len(response_saffier.json()) == 25

    # Check edgy again
    response_edgy = await async_client.get(
        "/products", headers={"tenant": "edgy", "email": "edgy@esmerald.dev"}
    )
    assert response_edgy.status_code == 200

    assert len(response_edgy.json()) == 10

    response = await async_cli.get("/no-tenant/products")
    assert response.status_code == 200
    assert len(response.json()) == 25


async def test_active_schema_user():
    tenant = await Tenant.query.create(schema_name="edgy", tenant_name="Edgy")
    user = await User.query.create(name="edgy", email="edgy@esmerald.dev")
    tenant_user = await TenantUser.query.create(user=user, tenant=tenant, is_active=True)

    await tenant_user.tenant.load()

    active_user_tenant = await TenantUser.get_active_user_tenant(user)
    assert active_user_tenant.tenant_uuid == tenant_user.tenant.tenant_uuid
    assert str(active_user_tenant.tenant_uuid) == str(tenant_user.tenant.tenant_uuid)


async def test_can_be_tenant_of_multiple_users():
    tenant = await Tenant.query.create(schema_name="edgy", tenant_name="Edgy")

    for i in range(3):
        user = await User.query.create(name=f"user-{i}", email=f"user-{i}@esmerald.dev")
        await TenantUser.query.create(user=user, tenant=tenant, is_active=True)

    total = await tenant.tenant_users_tenant_test.count()

    assert total == 3


async def test_multiple_tenants_one_active():
    # Tenant 1
    tenant = await Tenant.query.create(schema_name="edgy", tenant_name="Edgy")
    user = await User.query.create(name="edgy", email="edgy@esmerald.dev")
    tenant_user = await TenantUser.query.create(user=user, tenant=tenant, is_active=True)

    await tenant_user.tenant.load()

    active_user_tenant = await TenantUser.get_active_user_tenant(user)
    assert active_user_tenant.tenant_uuid == tenant_user.tenant.tenant_uuid

    # Tenant 2
    another_tenant = await Tenant.query.create(
        schema_name="another_edgy", tenant_name="Another Edgy"
    )
    await TenantUser.query.create(user=user, tenant=another_tenant, is_active=True)

    # Tenant 2
    another_tenant_three = await Tenant.query.create(
        schema_name="another_edgy_three", tenant_name="Another Edgy Three"
    )
    await TenantUser.query.create(user=user, tenant=another_tenant_three, is_active=True)

    active_user_tenant = await TenantUser.get_active_user_tenant(user)

    assert active_user_tenant.tenant_uuid == another_tenant_three.tenant_uuid
    assert active_user_tenant.tenant_uuid != another_tenant.tenant_uuid
    assert active_user_tenant.tenant_uuid != tenant.tenant_uuid
