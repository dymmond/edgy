import pytest

import edgy
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
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback(True):
        async with models:
            yield


class Test: ...


async def test_raise_prefetch_related_error():
    await User.query.create(name="Edgy")

    with pytest.raises(QuerySetError):
        await User.query.prefetch_related(
            Test(),
        ).all()
