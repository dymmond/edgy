from collections.abc import AsyncGenerator

import pytest
from anyio import from_thread, sleep, to_thread
from esmerald import Esmerald, Gateway, post
from httpx import ASGITransport, AsyncClient

import edgy
from edgy.core.marshalls import ConfigMarshall, Marshall, fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_connections():
    async with models:
        yield


def blocking_function():
    from_thread.run(sleep, 0.1)


class User(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=False)
    name: str = edgy.CharField(max_length=100, primary_key=True)
    email: str = edgy.EmailField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


class UserMarshall(Marshall):
    marshall_config = ConfigMarshall(model=User, fields=["name"])
    id: int = fields.MarshallField(field_type=int, source="id")
    name: str = fields.MarshallField(field_type=str, source="name")


@post("/create")
async def create_user(data: UserMarshall) -> UserMarshall:
    return data


@pytest.fixture()
def app():
    app = Esmerald(
        routes=[Gateway(handler=create_user)],
        on_startup=[database.connect],
        on_shutdown=[database.disconnect],
    )
    return app


@pytest.fixture()
async def async_client(app) -> AsyncGenerator:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await to_thread.run_sync(blocking_function)
        yield ac


async def test_simple_marshall(async_client):
    data = {
        "id": 123,
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
    }
    response = await async_client.post("/create", json=data)
    assert response.status_code == 201
    assert response.json() == {"id": 123, "name": "Edgy"}
