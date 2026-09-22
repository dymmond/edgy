import pytest

import edgy
from edgy.core.db.querysets import Prefetch
from edgy.exceptions import QuerySetError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Post(edgy.StrictModel):
    user = edgy.ForeignKey(User, related_name="posts")
    comment = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class Article(edgy.StrictModel):
    user = edgy.ForeignKey(User, related_name="articles")
    content = edgy.CharField(max_length=255)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


class Test: ...


@pytest.mark.parametrize("related_name", ["", "+", "+posts", "name"])
async def test_invalid_related_name(related_name):
    await User.query.create(name="Edgy")
    with pytest.raises(QuerySetError):
        await User.query.prefetch_related(
            Prefetch(related_name=related_name, to_attr="posts"),
        ).all()


@pytest.mark.parametrize("to_attr", ["", "+", "++posts"])
async def test_invalid_to_attr(to_attr):
    with pytest.raises(ValueError):
        Prefetch(related_name="posts", to_attr=to_attr)


@pytest.mark.parametrize("to_attr", ["name", "posts__comment", "name__post"])
async def test_invalid_to_attr2(to_attr):
    await User.query.create(name="Edgy")
    with pytest.raises(QuerySetError):
        await User.query.prefetch_related(
            Prefetch(related_name="posts", to_attr=to_attr),
        ).all()


async def test_multiple_prefetch_model_calls():
    await User.query.create(name="Edgy")

    with pytest.raises(QuerySetError):
        await User.query.prefetch_related(
            Prefetch(related_name="posts", to_attr="posts"),
            Prefetch(related_name="articles", to_attr="articles"),
        ).all()


async def test_raise_prefetch_related_error():
    await User.query.create(name="Edgy")

    with pytest.raises(QuerySetError):
        await User.query.prefetch_related(
            Test(),
        ).all()
