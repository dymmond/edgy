import asyncio
import datetime

import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    name: str = edgy.CharField(max_length=255)
    created_at: datetime.datetime = edgy.DateTimeField(auto_now_add=True)
    updated_at: datetime.datetime = edgy.DateTimeField(auto_now=True)

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


async def test_creates_and_updates_only_updated_at():
    user = await User.query.create(name="Test")
    assert user.created_at.tzinfo is None
    assert user.updated_at.tzinfo is None

    last_created_datetime = user.created_at
    last_updated_datetime = user.updated_at

    await asyncio.sleep(0.5)

    await user.update(name="Test 2")

    assert user.created_at == last_created_datetime
    assert user.updated_at != last_updated_datetime
    assert user.created_at.tzinfo is None
    assert user.updated_at.tzinfo is None


async def test_creates_and_updates_only_updated_at_on_save():
    user = await User.query.create(name="Test")

    last_created_datetime = user.created_at
    last_updated_datetime = user.updated_at

    await asyncio.sleep(0.5)

    user.name = "Test 2"
    await user.save()

    assert user.name == "Test 2"
    assert user.created_at == last_created_datetime
    assert user.updated_at != last_updated_datetime
