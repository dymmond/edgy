from collections.abc import AsyncGenerator, Coroutine
from typing import Any

import pytest
from anyio import from_thread, sleep, to_thread
from httpx import ASGITransport, AsyncClient
from lilya.types import ASGIApp, Receive, Scope, Send
from ravyn import Gateway, Ravyn, Request, get
from ravyn.core.protocols.middleware import MiddlewareProtocol

import edgy
from edgy.contrib.multi_tenancy import TenantModel
from edgy.contrib.multi_tenancy.models import TenantMixin, TenantUserMixin
from edgy.core.db import fields, with_tenant
from edgy.exceptions import ObjectNotFound
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


pytestmark = pytest.mark.anyio


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


class TenantUser(TenantUserMixin):
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

        try:
            user = await Tenant.query.get(schema_name=tenant_header)
            tenant = user.schema_name
        except ObjectNotFound:
            tenant = None

        with with_tenant(tenant):
            await self.app(scope, receive, send)


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models:
        yield


def blocking_function():
    from_thread.run(sleep, 0.1)


@get("/products")
async def get_products() -> list[Product]:
    products = await Product.query.all()
    return products


@pytest.fixture()
def app():
    app = models.asgi(
        Ravyn(
            routes=[Gateway(handler=get_products)],
            middleware=[TenantMiddleware],
        )
    )
    return app


@pytest.fixture()
def another_app():
    app = Ravyn(
        routes=[Gateway("/no-tenant", handler=get_products)],
        on_startup=[models.__aenter__],
        on_shutdown=[models.__aexit__],
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
    saffier = await User.query.create(name="saffier")

    edgy_tenant = await Tenant.query.create(schema_name="edgy", tenant_name="edgy")
    edgy = await User.query.using(schema=edgy_tenant.schema_name).create(name="edgy")

    await TenantUser.query.create(user=edgy, tenant=edgy_tenant)

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
    response_edgy = await async_client.get("/products", headers={"tenant": "edgy"})
    assert response_edgy.status_code == 200

    assert len(response_edgy.json()) == 10

    # Test Edgy Response intercepted in the
    response_saffier = await async_client.get("/products")
    assert response_saffier.status_code == 200

    assert len(response_saffier.json()) == 25

    # Check edgy again
    response_edgy = await async_client.get("/products", headers={"tenant": "edgy"})
    assert response_edgy.status_code == 200

    assert len(response_edgy.json()) == 10

    response = await async_cli.get("/no-tenant/products")
    assert response.status_code == 200
    assert len(response.json()) == 25
