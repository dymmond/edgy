import pytest

import edgy
from edgy.contrib.pagination import CursorPaginator, Paginator
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

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
    async with database:
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
        CounterTricky.query.order_by("-cursor2"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="prev",
    )
    assert (await paginator.get_page()).content[0].cursor2 == 99.0


async def test_pagination_int_count():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    paginator = Paginator(
        IntCounter.query.order_by("-id"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="prev",
    )
    assert await paginator.get_total() == 100
    assert paginator.queryset._order_by == ("-id",)
    assert paginator.get_reverse_paginator().queryset._order_by == ("id",)
    assert paginator.get_reverse_paginator().page_size == 30
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].id == 99
    assert arr[0].content[-1].id == 70
    assert arr[3].content[-1].id == 0
    assert arr[0].is_first
    assert arr[3].is_last
    assert arr[0].content[1].prev is arr[0].content[0]
    assert arr[0].content[0].next is arr[0].content[1]


async def test_pagination_int_count_double():
    await IntCounter2.query.bulk_create([{"id": 10, "id2": i} for i in range(100)])
    paginator = Paginator(
        IntCounter2.query.order_by("-id", "-id2"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="prev",
    )
    assert await paginator.get_total() == 100
    assert paginator.queryset._order_by == ("-id", "-id2")
    assert paginator.get_reverse_paginator().queryset._order_by == ("id", "id2")
    assert paginator.get_reverse_paginator().page_size == 30
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].id == 10
    assert arr[0].content[0].id2 == 99
    assert arr[0].content[-1].id2 == 70
    assert arr[1].content[0].id2 == 69
    assert arr[2].content[0].id2 == 39
    assert arr[3].content[-1].id2 == 0
    assert len(arr[0].content) == 30
    assert arr[0].content[0].prev is None
    assert arr[3].content[-1].next is None
    assert len(arr[3].content) == 10
    assert arr[0].is_first
    assert arr[3].is_last
    assert arr[0].content[1].prev is arr[0].content[0]
    assert (await paginator.get_reverse_paginator().get_page(-1)).content[-1].id2 == 99
    assert (await paginator.get_page(-1)).content[-1].id2 == 0


async def test_pagination_int_cursor():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    assert await IntCounter.query.count() == 100
    paginator = CursorPaginator(
        IntCounter.query.order_by("-id"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="prev",
    )
    arr = [item async for item in paginator.paginate()]
    assert arr[0].content[0].id == 99
    assert arr[0].content[-1].id == 70
    assert arr[3].content[-1].id == 0
    assert arr[0].content[0].prev is None
    assert arr[3].content[-1].next is None
    assert len(arr[3].content) == 10
    assert arr[0].is_first
    assert arr[3].is_last
    assert arr[0].content[1].prev is arr[0].content[0]

    page = await paginator.get_page()
    assert page.is_first
    assert page.next_cursor == 70
    arr = [item async for item in paginator.paginate(start_cursor=page.next_cursor)]
    assert len(arr) == 3
    assert arr[0].content[0].id == 69
    assert arr[0].content[0].prev is not None
    assert arr[2].content[-1].next is None
    assert len(arr[2].content) == 10
    assert not arr[0].is_first
    assert arr[2].is_last
    assert (await paginator.get_page()).content[-1].id == 70
    assert (await paginator.get_page(page.next_cursor)).content[-1].id == 40
    assert (await paginator.get_reverse_paginator().get_page()).content[0].id == 0

    page_rev = await paginator.get_page(page.next_cursor, backward=True)
    assert page_rev.content[-1].id == 70
    assert page_rev.content[0].id == 99
    assert page_rev.is_first
    assert page_rev.next_cursor == 99
