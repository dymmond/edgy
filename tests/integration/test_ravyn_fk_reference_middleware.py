from collections.abc import AsyncGenerator

import pytest
from anyio import from_thread, sleep, to_thread
from httpx import ASGITransport, AsyncClient
from pydantic import __version__
from ravyn import Gateway, Ravyn, post

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio
pydantic_version = ".".join(__version__.split(".")[:2])


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
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


class PostRef(edgy.ModelRef):
    __related_name__ = "posts_set"
    comment: str


class User(edgy.StrictModel):
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)
    posts: PostRef = edgy.RefForeignKey(PostRef)

    class Meta:
        registry = models


class Post(edgy.StrictModel):
    user = edgy.ForeignKey("User")
    comment = edgy.CharField(max_length=255)

    class Meta:
        registry = models


@post("/create")
async def create_user(data: User) -> User:
    user = await data.save()
    posts = await Post.query.filter(user=user)
    return_user = user.model_dump(exclude={"posts"})
    return_user["total_posts"] = len(posts)
    return return_user


@pytest.fixture()
def app():
    app = Ravyn(
        routes=[Gateway(handler=create_user)],
        on_startup=[models.__aenter__],
        on_shutdown=[models.__aexit__],
    )
    return app


@pytest.fixture()
async def async_client(app) -> AsyncGenerator:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await to_thread.run_sync(blocking_function)
        yield ac


async def test_creates_a_user_raises_value_error(async_client):
    data = {
        "name": "Edgy",
        "email": "edgy@ravyn.dev",
        "language": "EN",
        "description": "A description",
        "posts": {"comment": "A comment"},
    }
    response = await async_client.post("/create", json=data)
    assert response.status_code == 400  # default from Ravyn POST
    assert response.json() == {
        "detail": "Validation failed for http://test/create with method POST.",
        "errors": [
            {
                "type": "list_type",
                "loc": ["posts"],
                "msg": "Input should be a valid list",
                "input": {"comment": "A comment"},
                "url": f"https://errors.pydantic.dev/{pydantic_version}/v/list_type",
            }
        ],
    }
