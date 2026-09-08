import asyncio

import pytest

import edgy
from edgy.core.db.querysets import Prefetch
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class IntrospectingModel(edgy.StrictModel):
    class Meta:
        registry = models
        abstract = True

    @classmethod
    async def from_sqla_row(cls, **kwargs) -> edgy.Model:
        prefetches = kwargs.get("prefetch_related")
        initial_dicts = None
        if prefetches:
            await asyncio.gather(*(prefetch._init_bake() for prefetch in prefetches))
            initial_dicts = [dict(prefetch._baked_results) for prefetch in prefetches]
        returnobj = await super().from_sqla_row(**kwargs)
        object.__setattr__(returnobj, "introspected_prefetches", prefetches)
        object.__setattr__(returnobj, "introspected_prefetches_initial_baked", initial_dicts)
        return returnobj


class User(IntrospectingModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Post(IntrospectingModel):
    user = edgy.ForeignKey(User, related_name="posts")
    comment = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class Article(IntrospectingModel):
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


async def test_multiple_prefetch_single_user_model_shared_cache():
    user = await User.query.create(name="Edgy")

    for i in range(5):
        await Post.query.create(comment=f"Comment number {i}", user=user)

    for i in range(50):
        await Article.query.create(content=f"Comment number {i}", user=user)
    del user

    prefetches = [
        Prefetch(related_name="posts", to_attr="to_posts"),
        Prefetch(related_name="articles", to_attr="to_articles"),
    ]
    users = await User.query.prefetch_related(*prefetches).all()

    assert len(users) == 1

    assert all(
        not prefetch._baked and "_baked_results" not in prefetch.__dict__
        for prefetch in prefetches
    )
    assert all(prefetch._baked_results for prefetch in users[0].introspected_prefetches)
    assert all(
        users[0].create_model_key() in prefetch_dict
        for prefetch_dict in users[0].introspected_prefetches_initial_baked
    )

    assert len(users[0].to_posts) == 5
    assert len(users[0].to_articles) == 50


async def test_multiple_prefetch_model_shared_cache():
    user = await User.query.create(name="Edgy")

    for i in range(5):
        await Post.query.create(comment=f"Comment number {i}", user=user)

    for i in range(50):
        await Article.query.create(content=f"Comment number {i}", user=user)

    ravyn = await User.query.create(name="Ravyn")

    for i in range(15):
        await Post.query.create(comment=f"Comment number {i}", user=ravyn)

    for i in range(20):
        await Article.query.create(content=f"Comment number {i}", user=ravyn)

    prefetches = [
        Prefetch(related_name="posts", to_attr="to_posts"),
        Prefetch(related_name="articles", to_attr="to_articles"),
    ]
    users = await User.query.prefetch_related(*prefetches).all()

    assert len(users) == 2
    assert all(
        not prefetch._baked and "_baked_results" not in prefetch.__dict__
        for prefetch in prefetches
    )
    assert all(
        prefetch._baked_results for _user in users for prefetch in _user.introspected_prefetches
    )

    assert users[0].introspected_prefetches is users[1].introspected_prefetches
    assert (
        users[0].introspected_prefetches[0]._baked_results
        is users[1].introspected_prefetches[0]._baked_results
    )
    assert (
        users[0].introspected_prefetches[1]._baked_results
        is users[1].introspected_prefetches[1]._baked_results
    )
    assert all(
        users[1].create_model_key() in prefetch_dict
        for prefetch_dict in users[1].introspected_prefetches_initial_baked
    )


@pytest.mark.parametrize("batch_size", [1, 100])
async def test_multiple_prefetch_model_calls(batch_size):
    user = await User.query.create(name="Edgy")

    for i in range(5):
        await Post.query.create(comment=f"Comment number {i}", user=user)

    for i in range(50):
        await Article.query.create(content=f"Comment number {i}", user=user)

    ravyn = await User.query.create(name="Ravyn")

    for i in range(15):
        await Post.query.create(comment=f"Comment number {i}", user=ravyn)

    for i in range(20):
        await Article.query.create(content=f"Comment number {i}", user=ravyn)

    prefetches = [
        Prefetch(related_name="posts", to_attr="to_posts"),
        Prefetch(related_name="articles", to_attr="to_articles"),
    ]
    users = await User.query.prefetch_related(*prefetches).batch_size(batch_size).all()

    assert len(users) == 2

    assert all(
        not prefetch._baked and "_baked_results" not in prefetch.__dict__
        for prefetch in prefetches
    )
    assert all(prefetch._baked_results for prefetch in users[0].introspected_prefetches)

    user1 = [value for value in users if value.pk == user.pk][0]
    assert len(user1.to_posts) == 5
    assert len(user1.to_articles) == 50

    user2 = [value for value in users if value.pk == ravyn.pk][0]
    assert len(user2.to_posts) == 15
    assert len(user2.to_articles) == 20
