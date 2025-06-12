import copy
import json
from base64 import urlsafe_b64decode
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from lilya.apps import Lilya
from lilya.routing import Include

import edgy
from edgy.contrib.admin import create_admin_app
from edgy.contrib.contenttypes import ContentType as BaseContentType
from edgy.contrib.permissions import BasePermission
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio


class ContentType(BaseContentType):
    by_system: bool = edgy.fields.BooleanField(default=False)

    class Meta:
        abstract = True
        no_admin_create = False

    @classmethod
    def get_admin_marshall_config(cls, *, phase: str, for_schema: bool) -> dict:
        return {"exclude": ["by_system"]}


models = edgy.Registry(
    database=DatabaseTestClient(DATABASE_URL, force_rollback=False, drop_database=True),
    with_content_type=ContentType,
)


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    # this creates and drops the database
    async with models:
        await models.create_all()
        yield


@pytest.fixture()
async def app():
    admin_app = create_admin_app()
    new_settings = copy.copy(edgy.monkay.settings)
    new_settings.admin_config = copy.copy(new_settings.admin_config)
    new_settings.admin_config.admin_prefix_url = "/foobar"
    app = models.asgi(
        Lilya(
            routes=[
                Include(
                    path="/foo",
                    app=admin_app,
                ),
                Include(
                    path="/foobar",
                    app=admin_app,
                ),
            ]
        )
    )
    with edgy.monkay.with_full_overwrite(
        settings=new_settings, instance=edgy.Instance(registry=models, app=app)
    ):
        yield app


@pytest.fixture()
async def async_client(app) -> AsyncGenerator:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(params=["/foo", "/foobar"])
def prefix_url(request):
    yield request.param


class User(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    # simple default
    active = edgy.fields.BooleanField(default=False)

    class Meta:
        registry = models


class Group(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    users = edgy.fields.ManyToMany(
        "User", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )
    content_type = edgy.fields.ExcludeField()

    class Meta:
        registry = models


class Permission(BasePermission):
    users = edgy.fields.ManyToMany(
        "User", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )
    groups = edgy.fields.ManyToMany(
        "Group", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )
    name_model: str = edgy.fields.CharField(max_length=100, null=True)
    obj = edgy.fields.ForeignKey("ContentType", null=True)
    content_type = edgy.fields.ExcludeField()

    class Meta:
        registry = models
        unique_together = [("name", "name_model", "obj")]


async def test_settings(app):
    assert edgy.monkay.settings.admin_config.admin_prefix_url == "/foobar"
    assert "ContentType" in models.admin_models
    assert not models.content_type.meta.abstract
    assert models.content_type.meta.in_admin is True
    assert models.content_type.meta.no_admin_create is False


async def test_dashboard(async_client, prefix_url):
    response = await async_client.get(prefix_url, follow_redirects=True)
    assert response.status_code == 200
    for model in models.admin_models:
        assert model in response.text

    response = await async_client.get(f"{prefix_url}/models", follow_redirects=True)
    assert response.status_code == 200
    for model in models.admin_models:
        assert model in response.text


async def test_models(async_client, prefix_url):
    for model in models.admin_models:
        response = await async_client.get(f"{prefix_url}/models/{model}")
        assert response.status_code == 200
        assert model in response.text


@pytest.mark.parametrize("model", models.admin_models)
async def test_models_create_and_delete(async_client, model, prefix_url):
    response = await async_client.post(
        f"{prefix_url}/models/{model}/create",
        data={"editor_data": '{"name": "foo1234", "by_system": true}'},
        follow_redirects=True,
    )
    assert response.status_code == 200
    # here we can create contenttypes
    assert model in response.text
    # titled
    assert "Id" in response.text
    assert "Name" in response.text
    assert "foo1234" in response.text
    assert response.url.path.startswith("/foobar")
    obj = await models.get_model(model).query.get(
        pk=json.loads(urlsafe_b64decode(response.url.path.rsplit("/")[-1]))
    )
    assert await obj.check_exist_in_db()
    if model not in {"Permission", "Group", "ContentType"}:
        assert obj.content_type is not None
    # check handling of extra attributes
    assert not getattr(obj, "by_system", False)

    response = await async_client.post(
        f"{prefix_url}/models/{model}/{response.url.path.rsplit('/')[-1]}/delete",
        follow_redirects=True,
    )
    assert response.url.path.rsplit("/")[-1] == model
    assert not await obj.check_exist_in_db()
