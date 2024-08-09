from typing import Any, AsyncGenerator, Dict

import pytest
from anyio import from_thread, sleep, to_thread
from esmerald import Esmerald, Gateway, post
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, __version__

import edgy
from edgy.core.marshalls import Marshall, fields
from edgy.core.marshalls.config import ConfigMarshall
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, test_prefix="")
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio
pydantic_version = __version__[:3]


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
    data: fields.MarshallMethodField = fields.MarshallMethodField(Dict[str, Any])

    def get_details(self, instance) -> str:
        return instance.get_name()

    def get_data(self, instance) -> Dict[str, Any]:
        item = Item(sku="1234", name="laptop", age=1)
        return item.model_dump()


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
