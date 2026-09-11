import pytest

import edgy
from edgy.core.db.querysets import Prefetch
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, drop_database=True, use_existing=False)
models = edgy.Registry(database=database)


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


class Reaction(edgy.StrictModel):
    post = edgy.ForeignKey(Post, related_name="reactions")
    body = edgy.CharField(max_length=255)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    # this creates and drops the database
    async with models:
        await models.create_all()
        yield


async def test_prefetch_pivot_all():
    user = await User.query.create(name="Edgy")
    post = await user.posts.create(body="edgy is the best ORM ever")
    await post.comments.create(body="is true")
    await post.comments.create(body="I like javascript")
    await post.reactions.create(body="is true")
    await post.reactions.create(body="I like javascript")

    post = await user.posts.create(body="ravyn can handle asgi on a top level")
    await post.comments.create(body="is true")
    await post.comments.create(body="is really true")
    await post.reactions.create(body="is true")
    await post.reactions.create(body="I like javascript")

    posts = (
        await Comment.query.select_related("post")
        .prefetch_related(
            Prefetch(to_attr="comments_filtered", related_name="comments", from_anchor="post"),
            Prefetch(to_attr="reactions_filtered", related_name="reactions", from_anchor="post"),
            Prefetch(to_attr="users_filtered", related_name="user", from_anchor="post"),
        )
        .update_embed_parent(("post", "origin_comment"))
    )
    assert len(posts) == 4
    assert len(posts[0].users_filtered) == 1
    assert len(posts[0].comments_filtered) == 2
    assert len(posts[2].comments_filtered) == 2
    assert len(posts[0].reactions_filtered) == 2
    assert len(posts[2].reactions_filtered) == 2


async def test_prefetch_mixed_pivot1():
    user = await User.query.create(name="Edgy")
    post = await user.posts.create(body="edgy is the best ORM ever")
    await post.comments.create(body="is true")
    await post.comments.create(body="I like javascript")
    await post.reactions.create(body="is true")
    await post.reactions.create(body="I like javascript")

    post = await user.posts.create(body="ravyn can handle asgi on a top level")
    await post.comments.create(body="is true")
    await post.comments.create(body="is really true")
    await post.reactions.create(body="is true")
    await post.reactions.create(body="I like javascript")
    posts = (
        await Comment.query.select_related("post")
        .prefetch_related(
            Prefetch(to_attr="post__comments_filtered", related_name="post__comments"),
            Prefetch(to_attr="reactions_filtered", related_name="reactions", from_anchor="post"),
            Prefetch(to_attr="users_filtered", related_name="user", from_anchor="post"),
        )
        .update_embed_parent(("post", "origin_comment"))
    )
    assert len(posts) == 4
    assert len(posts[0].users_filtered) == 1
    assert len(posts[0].comments_filtered) == 2
    assert len(posts[2].comments_filtered) == 2
    assert len(posts[0].reactions_filtered) == 2
    assert len(posts[2].reactions_filtered) == 2


async def test_prefetch_mixed_pivot2():
    user = await User.query.create(name="Edgy")
    post = await user.posts.create(body="edgy is the best ORM ever")
    await post.comments.create(body="is true")
    await post.comments.create(body="I like javascript")
    await post.reactions.create(body="is true")
    await post.reactions.create(body="I like javascript")

    post = await user.posts.create(body="ravyn can handle asgi on a top level")
    await post.comments.create(body="is true")
    await post.comments.create(body="is really true")
    await post.reactions.create(body="is true")
    await post.reactions.create(body="I like javascript")
    posts = (
        await Comment.query.select_related("post")
        .prefetch_related(
            Prefetch(to_attr="comments_filtered", related_name="comments", from_anchor="post"),
            Prefetch(to_attr="post__reactions_filtered", related_name="post__reactions"),
            Prefetch(to_attr="post__users_filtered", related_name="post__user"),
        )
        .update_embed_parent(("post", "origin_comment"))
    )
    assert len(posts) == 4
    assert len(posts[0].users_filtered) == 1
    assert len(posts[0].comments_filtered) == 2
    assert len(posts[2].comments_filtered) == 2
    assert len(posts[0].reactions_filtered) == 2
    assert len(posts[2].reactions_filtered) == 2


async def test_prefetch_select_related_pivot():
    user = await User.query.create(name="Edgy")
    post = await user.posts.create(body="edgy is the best ORM ever")
    await post.comments.create(body="is true")
    await post.comments.create(body="I like javascript edgy")
    await post.comments.create(body="I like python edgy")
    await post.reactions.create(body="is true")
    await post.reactions.create(body="I like javascript")

    post = await user.posts.create(body="ravyn can handle asgi on a top level")
    await post.comments.create(body="is true")
    await post.comments.create(body="is really true")
    await post.comments.create(body="totally true")
    await post.reactions.create(body="is true")
    await post.reactions.create(body="I like javascript")

    posts = await Post.query.select_related("user").prefetch_related(
        Prefetch(to_attr="comments_filtered", related_name="comments"),
        Prefetch(to_attr="reactions_filtered", related_name="reactions"),
    )
    assert len(posts) == 2
    assert len(posts[0].comments_filtered) == 3
    assert len(posts[1].comments_filtered) == 3
    assert len(posts[0].reactions_filtered) == 2
    assert len(posts[1].reactions_filtered) == 2
