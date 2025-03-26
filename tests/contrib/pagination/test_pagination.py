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

async def test_reverse():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    assert (await IntCounter.query.all())[0].id == 0
    assert (await IntCounter.query.first()).id == 0
    assert (await IntCounter.query.reverse().first()).id == 99
    assert (await IntCounter.query.reverse().last()).id == 0
    assert (await IntCounter.query.reverse().all().last()).id == 0
    assert (await IntCounter.query.reverse())[0].id == 99

async def test_pagination_int_count():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    paginator = Paginator(
        IntCounter.query.all(), page_size=30, next_item_attr="next", previous_item_attr="prev"
    )
    assert await paginator.get_total() == 100
    assert paginator.queryset._order_by == ("id",)
    assert paginator.get_reverse_paginator().queryset._order_by == ("-id",)
    assert paginator.get_reverse_paginator().page_size == 30
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
    assert (await paginator.get_reverse_paginator().get_page(-1)).content[0].id == 29
    assert (await paginator.get_page(-1)).content[-1].id == 99


async def test_pagination_int_single_page():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    paginator = Paginator(
        IntCounter.query.all(), page_size=0, next_item_attr="next", previous_item_attr="prev"
    )
    assert await paginator.get_total() == 100
    assert paginator.queryset._order_by == ("id",)
    assert paginator.get_reverse_paginator().queryset._order_by == ("-id",)
    assert paginator.get_reverse_paginator().page_size == 0
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].id == 0
    assert arr[0].content[-1].id == 99
    assert arr[0].is_first
    assert arr[0].is_last
    assert arr[0].content[1].prev is arr[0].content[0]
    last_page = await paginator.get_page(-1)
    rev_last_page = await paginator.get_reverse_paginator().get_page(-1)
    assert last_page.content[-1].id == 99
    assert (await paginator.get_reverse_paginator().get_page(1)).content[0].id == 99
    assert (await paginator.get_reverse_paginator().get_page(2)).content[0].id == 99
    assert rev_last_page.content[0].id == 99


async def test_pagination_int_single_counter_page():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    paginator = CursorPaginator(
        IntCounter.query.all(), page_size=0, next_item_attr="next", previous_item_attr="prev", cursor_def="id"
    )
    assert paginator.queryset._order_by == ("id",)
    assert paginator.get_reverse_paginator().queryset._order_by == ("-id",)
    assert paginator.get_reverse_paginator().page_size == 0
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].id == 0
    assert arr[0].content[-1].id == 99
    assert arr[0].is_first
    assert arr[0].is_last
    assert arr[0].content[1].prev is arr[0].content[0]
    # cursor is 1
    pseudo_page = await paginator.get_page(1)
    assert pseudo_page.content[0].id == 2
    assert pseudo_page.content[-1].id == 99

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

    page = await paginator.get_page()
    assert page.is_first
    assert page.next_cursor == 29
    arr = [item async for item in paginator.paginate(start_cursor=page.next_cursor)]
    assert len(arr) == 3
    assert arr[0].content[0].id == 30
    assert arr[0].content[0].prev is not None
    assert arr[2].content[-1].next is None
    assert len(arr[2].content) == 10
    assert not arr[0].is_first
    assert arr[2].is_last
    assert (await paginator.get_page()).content[-1].id == 29
    assert (await paginator.get_page(page.next_cursor)).content[-1].id == 59
    assert (await paginator.get_reverse_paginator().get_page()).content[0].id == 99

    page_rev = await paginator.get_page(page.next_cursor+1, reverse=True)
    assert page_rev.content[-1].id == 29
    assert page_rev.content[0].id == 0
    assert page_rev.is_first
    assert page_rev.next_cursor == 0

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

    page = await paginator.get_page()
    arr = [item async for item in paginator.paginate(start_cursor=page.next_cursor)]
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

    page = await paginator.get_page()
    arr = [item async for item in paginator.paginate(start_cursor=page.next_cursor)]
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

    page = await paginator.get_page()
    arr = [item async for item in paginator.paginate(start_cursor=page.next_cursor)]
    assert len(arr) == 3
    assert len(arr[2].content) == 10
    assert not arr[0].is_first
    assert arr[2].is_last
