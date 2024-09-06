from typing import AsyncGenerator

import pytest
from anyio import from_thread, sleep, to_thread
from esmerald import Esmerald, Gateway, post
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


def blocking_function():
    from_thread.run(sleep, 0.1)


class IdNameDesc(BaseModel):
    id: int
    name: str
    description: str


class User(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)
    # we hijack the test to test the CompositeField in esmerald context
    id_name_desc: IdNameDesc = edgy.CompositeField(
        inner_fields=[
            "id",
            "name",
            ("description", edgy.TextField(max_length=5000, null=True)),
        ],
        exclude=False,
        absorb_existing_fields=True,
        model=IdNameDesc,
    )

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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
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
        "id_name_desc": {
            "description": "A description",
            "id": 1,
            "name": "Edgy",
        },
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
            "id_name_desc": {
                "description": "A description",
                "id": i + 1,
                "name": "Edgy",
            },
            "language": "EN",
            "description": "A description",
            "id": i + 1,
        }
