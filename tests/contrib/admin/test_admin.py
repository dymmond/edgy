import json
from base64 import urlsafe_b64decode
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from lilya.apps import Lilya
from lilya.middleware import DefineMiddleware
from lilya.middleware.sessions import SessionMiddleware
from lilya.routing import Include

import edgy
from edgy.contrib.admin import create_admin_app
from edgy.contrib.permissions import BasePermission
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

models = edgy.Registry(
    database=DatabaseTestClient(DATABASE_URL, force_rollback=False, drop_database=True),
    with_content_type=True,
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
    app = Lilya(
        routes=[Include("", admin_app)],
        middleware=[
            DefineMiddleware(
                SessionMiddleware, secret_key=edgy.monkay.settings.admin_config.SECRET_KEY
            )
        ],
    )
    app = models.asgi(app)
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


class BaseGroup(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    content_type = edgy.fields.ExcludeField()

    class Meta:
        abstract = True
        in_admin = True
        no_admin_create = False


class Group(BaseGroup):
    users = edgy.fields.ManyToMany(
        "User", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )

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


class UserFK(edgy.StrictModel):
    # model with revisioning active
    user = edgy.ForeignKey("User", primary_key=True)
    created = edgy.DateTimeField(auto_now_add=True, remove_timezone=True, primary_key=True)
    revisioning = edgy.DateTimeField(auto_now=True, remove_timezone=True, primary_key=True)
    name = edgy.fields.CharField(max_length=100, default="")

    class Meta:
        registry = models


async def test_settings(app):
    assert edgy.monkay.settings.admin_config.admin_prefix_url is None
    assert "ContentType" in models.admin_models


async def test_inheritance(app):
    assert Permission.meta.in_admin is None
    assert Permission.meta.no_admin_create is None
    assert Group.meta.in_admin is True
    assert Group.meta.no_admin_create is False


async def test_dashboard(async_client):
    response = await async_client.get("/")
    assert response.status_code == 200
    for model in models.admin_models:
        assert model in response.text

    response = await async_client.get("/models")
    assert response.status_code == 200
    for model in models.admin_models:
        assert model in response.text


async def test_models(async_client):
    for model in models.admin_models:
        response = await async_client.get(f"/models/{model}")
        assert response.status_code == 200
        assert model in response.text


@pytest.mark.parametrize("model", models.admin_models)
async def test_models_create_and_delete(async_client, model):
    editor_data = {"name": "foo1234"}
    if model == "UserFK":
        u = await User.query.create(**editor_data)
        editor_data["user"] = u.id
    response = await async_client.post(
        f"/models/{model}/create",
        data={"editor_data": json.dumps(editor_data)},
        follow_redirects=True,
    )
    assert response.status_code == 200
    if model == "ContentType":
        assert response.url.path == "/models/ContentType"
        return
    else:
        assert model in response.text
        assert "Id" in response.text
        assert "Name" in response.text
        assert "foo1234" in response.text
    pkob = json.loads(urlsafe_b64decode(response.url.path.rsplit("/")[-1]))
    obj = await models.get_model(model).query.get(pk=pkob)
    assert await obj.check_exist_in_db()
    if model not in {"Permission", "Group", "ContentType"}:
        assert obj.content_type is not None

    response = await async_client.post(
        f"/models/{model}/{response.url.path.rsplit('/')[-1]}/delete",
        follow_redirects=True,
    )
    assert response.url.path.rsplit("/")[-1] == model
    assert not await obj.check_exist_in_db()
