import pytest

import edgy
from edgy.core.db.querysets import Prefetch
from edgy.exceptions import QuerySetError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
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
    async with database:
        await models.create_all()
        yield
    await models.drop_all()


async def test_multiple_prefetch_model_calls():
    await User.query.create(name="Edgy")

    with pytest.raises(QuerySetError):
        await User.query.prefetch_related(
            Prefetch(related_name="posts", to_attr="posts"),
            Prefetch(related_name="articles", to_attr="articles"),
        ).all()
