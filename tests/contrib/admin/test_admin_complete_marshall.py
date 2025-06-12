import json
from base64 import urlsafe_b64decode
from collections.abc import AsyncGenerator
from typing import ClassVar

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ConfigDict

import edgy
from edgy.contrib.admin import create_admin_app
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

models = edgy.Registry(
    database=DatabaseTestClient(DATABASE_URL, force_rollback=False, drop_database=True),
)


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    # this creates and drops the database
    async with models:
        await models.create_all()
        yield


@pytest.fixture()
async def app():
    app = models.asgi(create_admin_app())
    with edgy.monkay.with_full_overwrite(instance=edgy.Instance(registry=models, app=app)):
        yield app


@pytest.fixture()
async def async_client(app) -> AsyncGenerator:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class User(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    # simple default
    active = edgy.fields.BooleanField(default=False)

    class Meta:
        registry = models

    @classmethod
    def get_admin_marshall_config(cls, *, phase: str, for_schema: bool) -> dict:
        return {"exclude": ["name" if phase == "update" else "active"]}

    @classmethod
    def get_admin_marshall_class(
        cls: type[edgy.Model], *, phase: str, for_schema: bool = False
    ) -> type[edgy.marshalls.Marshall]:
        class AdminMarshall(edgy.marshalls.Marshall):
            model_config: ClassVar[ConfigDict] = ConfigDict(
                title=cls.__name__, extra="forbid" if for_schema else None
            )
            marshall_config = edgy.marshalls.ConfigMarshall(
                model=cls,
                **cls.get_admin_marshall_config(phase=phase, for_schema=for_schema),  # type: ignore
            )
            active: bool = True
            kabooo: edgy.marshalls.MarshallMethodField = edgy.marshalls.MarshallMethodField(
                field_type=str
            )

            def get_kabooo(self, instance) -> str:
                return f"{instance}4565"

        return AdminMarshall


async def test_model_fields(async_client):
    marshall_class = User.get_admin_marshall_class(phase="view")
    assert "kabooo" in marshall_class.model_fields
    assert "kabooo" not in User.model_fields


async def test_models(async_client):
    assert "User" in models.admin_models
    response = await async_client.get("/models/User")
    assert response.status_code == 200
    assert "User" in response.text


async def test_models_create_and_delete(async_client):
    response = await async_client.post(
        "/models/User/create",
        data={"editor_data": '{"name": "foo1234"}'},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "User" in response.text
    # titled
    assert "Id" in response.text
    assert "Name" in response.text
    assert "Kabooo" in response.text
    assert "4565" in response.text
    assert "foo1234" in response.text
    obj = await models.get_model("User").query.get(
        pk=json.loads(urlsafe_b64decode(response.url.path.rsplit("/")[-1]))
    )
    assert await obj.check_exist_in_db()
    assert obj.active

    response = await async_client.post(
        f"/models/User/{response.url.path.rsplit('/')[-1]}/delete",
        follow_redirects=True,
    )
    assert response.url.path.rsplit("/")[-1] == "User"
    assert not await obj.check_exist_in_db()
