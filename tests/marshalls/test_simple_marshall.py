from collections.abc import AsyncGenerator

import pytest
from esmerald import Esmerald, post
from httpx import ASGITransport, AsyncClient

import edgy
from edgy.core.marshalls import ConfigMarshall, Marshall
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


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


class UserMarshall(Marshall):
    marshall_config = ConfigMarshall(model=User, fields=["id", "name"])


class UserUpdateMarshall(Marshall):
    marshall_config = ConfigMarshall(model=User, fields=["email"])


@post("/create")
async def create_user(data: UserMarshall) -> UserMarshall:
    await data.save()
    return data


@post("/update/{id}")
async def update_user(id: int, data: UserUpdateMarshall) -> UserUpdateMarshall:
    data.instance = await User.query.get(id=id)
    await data.save()
    return data


@pytest.fixture()
def app():
    app = Esmerald(
        routes=[create_user, update_user],
        on_startup=[database.connect],
        on_shutdown=[database.disconnect],
    )
    return app


@pytest.fixture()
async def async_client(app) -> AsyncGenerator:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_simple_marshall(async_client):
    data = {
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
    }
    response = await async_client.post("/create", json=data)
    assert response.status_code == 201
    result = response.json()
    result.pop("id")
    assert result == {"name": "Edgy"}


async def test_simple_marshall_update(async_client):
    data = {
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
    }
    response = await async_client.post("/create", json=data)
    assert response.status_code == 201
    result = response.json()
    id = result.pop("id")
    data["email"] = "edgy@esmerald.foo"

    response = await async_client.post(f"/update/{id}", json=data)
    assert response.json() == {"email": "edgy@esmerald.foo"}
