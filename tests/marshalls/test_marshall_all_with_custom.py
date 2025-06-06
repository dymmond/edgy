from collections.abc import AsyncGenerator
from typing import Any

import pytest
from anyio import from_thread, sleep, to_thread
from esmerald import Esmerald, Gateway, post
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

import edgy
from edgy.core.marshalls import Marshall, fields
from edgy.core.marshalls.config import ConfigMarshall
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
    name: str = edgy.CharField(max_length=100, null=True)
    email: str = edgy.EmailField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models

    def get_name(self) -> str:
        return f"Details about {self.name}"

    @property
    def age(self) -> int:
        return 2


class Item(BaseModel):
    sku: str
    name: str
    age: int


class UserMarshall(Marshall):
    marshall_config = ConfigMarshall(model=User, fields=["__all__"])
    details: fields.MarshallMethodField = fields.MarshallMethodField(field_type=str)
    age: fields.MarshallField = fields.MarshallField(int, source="age")
    data: fields.MarshallMethodField = fields.MarshallMethodField(dict[str, Any])

    shall_save: bool = Field(default=False, exclude=True)

    def get_details(self, instance) -> str:
        return instance.get_name()

    def get_data(self, instance) -> dict[str, Any]:
        item = Item(sku="1234", name="laptop", age=1)
        return item.model_dump()


@post("/create")
async def create_user(data: UserMarshall) -> UserMarshall:
    if data.shall_save:
        await data.save()
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


async def test_marshall_all_with_custom_fields(async_client):
    data = {
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
    }
    response = await async_client.post("/create", json=data)
    assert response.status_code == 201
    assert response.json() == {
        "id": None,
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
        "details": "Details about Edgy",
        "age": 2,
        "data": {"sku": "1234", "name": "laptop", "age": 1},
    }


async def test_marshall_all_with_custom_fields_and_extra(async_client):
    data = {
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
        "shall_save": True,
    }
    response = await async_client.post("/create", json=data)
    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
        "details": "Details about Edgy",
        "age": 2,
        "data": {"sku": "1234", "name": "laptop", "age": 1},
    }


async def test_seperate_pydantic_and_custom():
    assert "shall_save" in UserMarshall.model_fields
    assert "shall_save" not in UserMarshall.__custom_fields__
