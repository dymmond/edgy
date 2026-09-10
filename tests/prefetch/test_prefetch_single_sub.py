import pytest

import edgy
from edgy.core.db.querysets import Prefetch
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
    body = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class Comment(edgy.StrictModel):
    post = edgy.ForeignKey(Post, related_name="comments")
    body = edgy.CharField(max_length=255)

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


async def test_prefetch_select_related():
    user = await User.query.create(name="Edgy")
    post = await user.posts.create(body="edgy is the best ORM ever")
    await post.comments.create(body="is true")
    await post.comments.create(body="I like javascript")

    post = await user.posts.create(body="ravyn can handle asgi on a top level")
    await post.comments.create(body="is true")
    await post.comments.create(body="is really true")

    posts = (
        await Comment.query.select_related("post")
        .prefetch_related(
            Prefetch(to_attr="comments_filtered", related_name="comments", anchor_path="post"),
            Prefetch(to_attr="post__users_filtered", related_name="post__user"),
        )
        .update_embed_parent(("post", "origin_comment"))
    )
    assert len(posts) == 4
    assert len(posts[0].comments_filtered)
    assert len(posts[2].comments_filtered)
