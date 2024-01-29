import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.exceptions import QuerySetError
from edgy.testclient import DatabaseTestClient as Database

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL)
models = edgy.Registry(database=database)


class User(edgy.Model):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Post(edgy.Model):
    user = edgy.ForeignKey(User, related_name="posts")
    comment = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class Article(edgy.Model):
    user = edgy.ForeignKey(User, related_name="articles")
    content = edgy.CharField(max_length=255)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


class Test: ...


async def test_raise_prefetch_related_error():
    await User.query.create(name="Edgy")

    with pytest.raises(QuerySetError):
        await User.query.prefetch_related(
            Test(),
        ).all()
