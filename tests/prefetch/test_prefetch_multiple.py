import pytest

import edgy
from edgy.core.db.querysets import Prefetch
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


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


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models.database:
        yield


async def test_multiple_prefetch_model_calls():
    user = await User.query.create(name="Edgy")

    for i in range(5):
        await Post.query.create(comment=f"Comment number {i}", user=user)

    for i in range(50):
        await Article.query.create(content=f"Comment number {i}", user=user)

    esmerald = await User.query.create(name="Esmerald")

    for i in range(15):
        await Post.query.create(comment=f"Comment number {i}", user=esmerald)

    for i in range(20):
        await Article.query.create(content=f"Comment number {i}", user=esmerald)

    users = await User.query.prefetch_related(
        Prefetch(related_name="posts", to_attr="to_posts"),
        Prefetch(related_name="articles", to_attr="to_articles"),
    ).all()

    assert len(users) == 2

    user1 = [value for value in users if value.pk == user.pk][0]
    assert len(user1.to_posts) == 5
    assert len(user1.to_articles) == 50

    user2 = [value for value in users if value.pk == esmerald.pk][0]
    assert len(user2.to_posts) == 15
    assert len(user2.to_articles) == 20
