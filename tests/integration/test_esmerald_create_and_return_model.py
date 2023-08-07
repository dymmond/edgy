from typing import AsyncGenerator

import pytest
from anyio import from_thread, sleep, to_thread
from esmerald import Esmerald, Gateway, post
from httpx import AsyncClient
from tests.settings import DATABASE_URL

import edgy
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="function")
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


class User(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


@post("/create")
async def create_user(data: User) -> User:
    user = await data.save()
    return user


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
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await to_thread.run_sync(blocking_function)
        yield ac


async def test_creates_a_user_directly(async_client):
    data = {
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
    }
    response = await async_client.post("/create", json=data)
    assert response.status_code == 201  # default from Esmerald POST
    assert response.json() == {
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
        "id": 1,
    }


async def test_creates_many_users(async_client):
    data = {
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
    }

    for i in range(5):
        response = await async_client.post("/create", json=data)
        assert response.status_code == 201  # default from Esmerald POST
        assert response.json() == {
            "name": "Edgy",
            "email": "edgy@esmerald.dev",
            "language": "EN",
            "description": "A description",
            "id": i + 1,
        }
