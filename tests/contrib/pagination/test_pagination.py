import pytest

import edgy
from edgy.contrib.pagination import CursorPaginator, Paginator
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, force_rollback=True)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class IntCounter(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=False)

    class Meta:
        registry = models


class FloatCounter(edgy.Model):
    id: float = edgy.FloatField(primary_key=True, autoincrement=False)

    class Meta:
        registry = models


class StrCounter(edgy.Model):
    id: str = edgy.CharField(primary_key=True, max_length=20)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_connection():
    async with models:
        yield


async def test_pagination_int_count():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    assert await IntCounter.query.count() == 100
    paginator = Paginator(
        IntCounter.query.all(), page_size=30, next_item_attr="next", previous_item_attr="prev"
    )
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].id == 0
    assert arr[0].content[-1].id == 29
    assert arr[1].content[0].id == 30
    assert arr[2].content[0].id == 60
    assert arr[3].content[-1].id == 99
    assert len(arr[0].content) == 30
    assert arr[0].content[0].prev is None
    assert arr[3].content[-1].next is None
    assert len(arr[3].content) == 10
    assert arr[0].is_first
    assert arr[3].is_last
    assert arr[0].content[1].prev is arr[0].content[0]
    assert (await paginator.get_page(-1)).content[-1].id == 99


async def test_pagination_int_count_no_attrs():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    assert await IntCounter.query.count() == 100
    paginator = Paginator(IntCounter.query.all(), page_size=30)
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].id == 0
    assert arr[0].content[-1].id == 29
    assert arr[1].content[0].id == 30
    assert arr[2].content[0].id == 60
    assert arr[3].content[-1].id == 99
    assert len(arr[0].content) == 30
    assert len(arr[3].content) == 10
    assert arr[0].is_first
    assert arr[3].is_last
    assert (await paginator.get_page(-1)).content[-1].id == 99


async def test_pagination_int_cursor():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    assert await IntCounter.query.count() == 100
    paginator = CursorPaginator(
        IntCounter.query.all(),
        page_size=30,
        cursor_def="id",
        next_item_attr="next",
        previous_item_attr="prev",
    )
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].id == 0
    assert arr[0].content[-1].id == 29
    assert arr[1].content[0].id == 30
    assert arr[2].content[0].id == 60
    assert arr[3].content[-1].id == 99
    assert arr[0].content[0].prev is None
    assert arr[3].content[-1].next is None
    assert len(arr[3].content) == 10
    assert arr[0].is_first
    assert arr[3].is_last
    assert arr[0].content[1].prev is arr[0].content[0]

    page, cursor = await paginator.get_page()
    assert cursor == 29
    arr = [item async for item in paginator.paginate(start_cursor=cursor)]
    assert len(arr) == 3
    assert arr[0].content[0].id == 30
    assert arr[0].content[0].prev is not None
    assert arr[2].content[-1].next is None
    assert len(arr[2].content) == 10
    assert not arr[0].is_first
    assert arr[2].is_last


async def test_pagination_float_cursor():
    await FloatCounter.query.bulk_create([{"id": i / 1.324} for i in range(100)])
    assert await FloatCounter.query.count() == 100
    paginator = CursorPaginator(
        FloatCounter.query.all(),
        page_size=30,
        cursor_def="id",
        next_item_attr="next",
        previous_item_attr="prev",
    )
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].prev is None
    assert arr[3].content[-1].next is None
    assert len(arr[3].content) == 10
    assert arr[0].is_first
    assert arr[3].is_last
    assert arr[0].content[1].prev is arr[0].content[0]

    page, cursor = await paginator.get_page()
    arr = [item async for item in paginator.paginate(start_cursor=cursor)]
    assert len(arr) == 3
    assert arr[0].content[0].prev is not None
    assert arr[2].content[-1].next is None
    assert len(arr[2].content) == 10
    assert not arr[0].is_first
    assert arr[2].is_last


async def test_pagination_str_cursor():
    await StrCounter.query.bulk_create([{"id": f"{i:04}"} for i in range(100)])
    assert await StrCounter.query.count() == 100
    paginator = CursorPaginator(
        StrCounter.query.all(),
        page_size=30,
        cursor_def="id",
        next_item_attr="next",
        previous_item_attr="prev",
    )
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].prev is None
    assert arr[3].content[-1].next is None
    assert len(arr[3].content) == 10
    assert arr[0].is_first
    assert arr[3].is_last
    assert arr[0].content[1].prev is arr[0].content[0]

    page, cursor = await paginator.get_page()
    arr = [item async for item in paginator.paginate(start_cursor=cursor)]
    assert len(arr) == 3
    assert arr[0].content[0].prev is not None
    assert arr[2].content[-1].next is None
    assert len(arr[2].content) == 10
    assert not arr[0].is_first
    assert arr[2].is_last


async def test_pagination_str_cursor_no_attrs():
    await StrCounter.query.bulk_create([{"id": f"{i:04}"} for i in range(100)])
    assert await StrCounter.query.count() == 100
    paginator = CursorPaginator(
        StrCounter.query.all(),
        page_size=30,
        cursor_def="id",
    )
    arr = [item async for item in paginator.paginate()]
    assert len(arr[3].content) == 10
    assert arr[0].is_first
    assert arr[3].is_last

    page, cursor = await paginator.get_page()
    arr = [item async for item in paginator.paginate(start_cursor=cursor)]
    assert len(arr) == 3
    assert len(arr[2].content) == 10
    assert not arr[0].is_first
    assert arr[2].is_last
