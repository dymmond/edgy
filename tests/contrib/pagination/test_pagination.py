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


class IntCounter2(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=False)
    id2: int = edgy.IntegerField(primary_key=True, autoincrement=False)

    class Meta:
        registry = models


class CounterTricky(edgy.Model):
    cursor: float = edgy.FloatField(unique=True)
    cursor2: float = edgy.FloatField(unique=True, null=True)

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


async def test_pagination_tricky():
    await CounterTricky.query.bulk_create([{"cursor": i / 1.1, "cursor2": i} for i in range(100)])
    paginator = Paginator(
        CounterTricky.query.order_by("cursor2"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="prev",
    )
    page = await paginator.get_page()
    assert page.content[0].cursor2 == 0.0

    with pytest.raises(KeyError):
        await CursorPaginator(
            CounterTricky.query.order_by("non_exist"),
            page_size=30,
            next_item_attr="next",
            previous_item_attr="prev",
        ).get_page()


async def test_pagination_int_count_no_leak():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    ordered = IntCounter.query.order_by("-id")
    await ordered.count()
    paginator = Paginator(ordered, page_size=0, next_item_attr="next", previous_item_attr="prev")
    # this shall be passed
    assert paginator.queryset._cache_count is not None
    entries_ordered = await ordered
    entries_paginator = list((await paginator.get_page()).content)
    assert all(not hasattr(entry, "next") for entry in entries_ordered)
    assert all(not hasattr(entry, "prev") for entry in entries_ordered)
    assert all(hasattr(entry, "next") for entry in entries_paginator)
    assert all(hasattr(entry, "prev") for entry in entries_paginator)
    assert len(entries_ordered) == len(entries_paginator)
    assert all(entry1 == entry2 for entry1, entry2 in zip(entries_ordered, entries_paginator))


async def test_pagination_int_count_no_copy():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    ordered = IntCounter.query.order_by("-id")
    paginator = Paginator(ordered, page_size=0)
    await ordered
    assert paginator.queryset._cache_fetch_all


@pytest.mark.parametrize("paginator_class", [Paginator, CursorPaginator])
async def test_page_model_dump(paginator_class):
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    ordered = IntCounter.query.order_by("-id")
    paginator = paginator_class(ordered, page_size=0)
    counter_page = await paginator.get_page()
    counter_page.model_dump()


async def test_pagination_int_count():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    paginator = Paginator(
        IntCounter.query.order_by("id"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="prev",
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
    assert arr[0].content[0].next is arr[0].content[1]
    assert (await paginator.get_reverse_paginator().get_page(-1)).content[0].id == 29
    assert (await paginator.get_page(-1)).content[-1].id == 99


async def test_pagination_int_count_double():
    await IntCounter2.query.bulk_create([{"id": 10, "id2": i} for i in range(100)])
    paginator = Paginator(
        IntCounter2.query.order_by("id", "id2"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="prev",
    )
    assert await paginator.get_total() == 100
    assert paginator.queryset._order_by == ("id", "id2")
    assert paginator.get_reverse_paginator().queryset._order_by == ("-id", "-id2")
    assert paginator.get_reverse_paginator().page_size == 30
    arr = [item async for item in paginator.paginate()]
    assert arr[0].previous_page is None
    assert arr[0].current_page == 1
    assert arr[0].next_page == 2
    assert arr[0].content[0].id == 10
    assert arr[0].content[0].id2 == 0
    assert arr[0].content[-1].id2 == 29
    assert arr[1].content[0].id2 == 30
    assert arr[2].content[0].id2 == 60
    assert arr[3].content[-1].id2 == 99
    assert len(arr[0].content) == 30
    assert arr[0].content[0].prev is None
    assert arr[3].content[-1].next is None
    assert len(arr[3].content) == 10
    assert arr[0].is_first
    assert arr[3].is_last
    assert arr[0].content[1].prev is arr[0].content[0]
    assert (await paginator.get_reverse_paginator().get_page(-1)).content[0].id2 == 29
    assert (await paginator.get_page(-1)).content[-1].id2 == 99


async def test_pagination_int_cursor_double():
    await IntCounter2.query.bulk_create([{"id": 10, "id2": i} for i in range(100)])
    paginator = CursorPaginator(
        IntCounter2.query.order_by("id", "id2"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="prev",
    )
    assert await paginator.get_total() == 100
    assert paginator.queryset._order_by == ("id", "id2")
    assert paginator.get_reverse_paginator().queryset._order_by == ("-id", "-id2")
    assert paginator.get_reverse_paginator().page_size == 30
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].id == 10
    assert arr[0].content[0].id2 == 0
    assert arr[0].content[-1].id2 == 29
    assert arr[1].content[0].id2 == 30
    assert arr[2].content[0].id2 == 60
    assert arr[3].content[-1].id2 == 99
    assert len(arr[0].content) == 30
    assert arr[0].content[0].prev is None
    assert arr[3].content[-1].next is None
    assert len(arr[3].content) == 10
    assert arr[0].is_first
    assert arr[3].is_last
    assert arr[0].content[1].prev is arr[0].content[0]

    page = await paginator.get_page()
    assert page.is_first
    assert page.next_cursor == (10, 29.0)
    arr = [item async for item in paginator.paginate(start_cursor=page.next_cursor)]
    assert len(arr) == 3
    assert arr[0].content[0].id2 == 30.0
    assert arr[0].content[0].prev is not None
    assert arr[2].content[-1].next is None
    assert len(arr[2].content) == 10
    assert not arr[0].is_first
    assert arr[2].is_last
    assert (await paginator.get_page()).content[-1].id2 == 29.0
    assert (await paginator.get_page(page.next_cursor)).content[-1].id2 == 59.0
    assert (await paginator.get_reverse_paginator().get_page()).content[0].id2 == 99.0

    page_rev = await paginator.get_page(page.next_cursor, backward=True)
    assert page_rev.current_cursor == page.next_cursor
    assert page_rev.content[-1].id2 == 29.0
    assert page_rev.content[0].id2 == 0.0
    assert page_rev.is_first
    assert page_rev.next_cursor == (10, 0)


async def test_pagination_int_single_page():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    paginator = Paginator(
        IntCounter.query.order_by("id"),
        page_size=0,
        next_item_attr="next",
        previous_item_attr="prev",
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
        IntCounter.query.order_by("id"),
        page_size=0,
        next_item_attr="next",
        previous_item_attr="prev",
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
    paginator = Paginator(IntCounter.query.order_by("id"), page_size=30)
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
        IntCounter.query.order_by("id"),
        page_size=30,
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

    page_rev = await paginator.get_page(page.next_cursor, backward=True)
    assert page_rev.content[-1].id == 29
    assert page_rev.content[0].id == 0
    assert page_rev.is_first
    assert page_rev.next_cursor == 0


async def test_pagination_float_cursor():
    await FloatCounter.query.bulk_create([{"id": i / 1.324} for i in range(100)])
    assert await FloatCounter.query.count() == 100
    paginator = CursorPaginator(
        FloatCounter.query.order_by("id"),
        page_size=30,
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
        StrCounter.query.order_by("id"),
        page_size=30,
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
        StrCounter.query.order_by("id"),
        page_size=30,
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
