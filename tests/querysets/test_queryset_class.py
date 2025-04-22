import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, force_rollback=True)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    name: str = edgy.CharField(max_length=100, null=True)

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
    async with models:
        yield


async def test_queryset_cache_all():
    users = await User.query.all()
    assert users == []

    user = await User.query.create(name="Test")
    query = User.query.all()
    query2 = query.all()
    assert query._cached_select_with_tables is None
    assert await query == [user]
    assert query._cache_fetch_all
    assert query._cached_select_with_tables is not None
    await query2
    await query2.create(name="Test2")
    # cached
    assert await query == [user]
    assert await query.get() is (await query)[0]
    # updated cache
    assert len(await query2) == 2
    query.all(True)
    assert query._cached_select_with_tables is not None
    returned_list = await query
    assert returned_list[0] is not user
    assert len(returned_list) == 2


async def test_queryset_cache_get():
    users = await User.query.all()
    assert users == []
    query = User.query.filter(name="Test")
    user = await query.create(name="Test")
    assert query._cache.cache
    assert user is await query.get()
