from typing import AsyncGenerator

import pytest
from anyio import from_thread, sleep, to_thread
from esmerald import Esmerald, Gateway, post
from httpx import AsyncClient
from pydantic import __version__

import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
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


class PostRef(edgy.ModelRef):
    __model__ = "Post"
    comment: str


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)
    posts: PostRef = edgy.RefForeignKey(PostRef)

    class Meta:
        registry = models


class Post(edgy.Model):
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


async def test_creates_a_user_raises_value_error(async_client):
    data = {
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
        "posts": {"comment": "A comment"},
    }
    response = await async_client.post("/create", json=data)
    assert response.status_code == 400  # default from Esmerald POST
    assert response.json() == {
        "detail": "Validation failed for http://test/create with method POST.",
        "errors": [
            {
                "type": "list_type",
                "loc": ["data", "posts"],
                "msg": "Input should be a valid list",
                "input": {"comment": "A comment"},
                "url": f"https://errors.pydantic.dev/{pydantic_version}/v/list_type",
            }
        ],
    }
