import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class IntCounter(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=False)
    criteria2: int = edgy.IntegerField(autoincrement=False, null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # creates/drops db
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_connection():
    # rollsback, different db
    async with models:
        yield


async def test_reverse_default():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    assert (await IntCounter.query.all())[0].id == 0
    assert (await IntCounter.query.first()).id == 0
    assert (await IntCounter.query.reverse().first()).id == 99
    assert (await IntCounter.query.reverse().last()).id == 0
    assert (await IntCounter.query.reverse().all().last()).id == 0
    assert (await IntCounter.query.reverse())[0].id == 99
    assert (await IntCounter.query.reverse().reverse())[0].id == 0


async def test_reverse_order_by():
    await IntCounter.query.bulk_create([{"id": i} for i in range(100)])
    assert (await IntCounter.query.order_by("id"))[0].id == 0
    assert (await IntCounter.query.order_by("id").first()).id == 0
    assert (await IntCounter.query.order_by("id").reverse().first()).id == 99
    assert (await IntCounter.query.order_by("id").reverse().last()).id == 0
    assert (await IntCounter.query.order_by("id").reverse().all().last()).id == 0
    assert (await IntCounter.query.order_by("id").reverse())[0].id == 99
    assert (await IntCounter.query.order_by("id").reverse().reverse())[0].id == 0

    await IntCounter.query.bulk_create([{"id": i, "criteria2": 1} for i in range(100, 200)])
    # nulls last
    assert (await IntCounter.query.order_by("criteria2", "id"))[0].id == 100
    assert (await IntCounter.query.order_by("-criteria2", "id"))[0].id == 0
    assert (await IntCounter.query.order_by("criteria2", "id").reverse())[0].id == 99
    assert (await IntCounter.query.order_by("-criteria2", "id").reverse())[0].id == 199
