import pytest

import edgy
from edgy.core.db.querysets import Prefetch
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


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


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
    # here the drop is required to be outside of the scope
    await models.drop_all()


async def test_multiple_prefetch_model_calls_iterate_no_rollback():
    with database.force_rollback(False):
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

        users = [
            user
            async for user in User.query.prefetch_related(
                Prefetch(related_name="posts", to_attr="to_posts"),
                Prefetch(related_name="articles", to_attr="to_articles"),
            )
        ]

        assert len(users) == 2

        user1 = [value for value in users if value.pk == user.pk][0]
        assert len(user1.to_posts) == 5
        assert len(user1.to_articles) == 50

        user2 = [value for value in users if value.pk == esmerald.pk][0]
        assert len(user2.to_posts) == 15
        assert len(user2.to_articles) == 20


async def test_multiple_prefetch_model_calls_iterate_force_rollback():
    with database.force_rollback():
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

        with pytest.warns(UserWarning):
            # it should warn agains the iterate feature in combination with force_rollback
            # and also mitigate this for the call
            users = [
                user
                async for user in User.query.prefetch_related(
                    Prefetch(related_name="posts", to_attr="to_posts"),
                    Prefetch(related_name="articles", to_attr="to_articles"),
                )
            ]

        assert len(users) == 2

        user1 = [value for value in users if value.pk == user.pk][0]
        assert len(user1.to_posts) == 5
        assert len(user1.to_articles) == 50

        user2 = [value for value in users if value.pk == esmerald.pk][0]
        assert len(user2.to_posts) == 15
        assert len(user2.to_articles) == 20
