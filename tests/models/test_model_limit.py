import pytest

import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_model_limit():
    await User.query.create(name="Test")
    await User.query.create(name="Jane")
    await User.query.create(name="Lucy")

    assert len(await User.query.limit(2).all()) == 2


async def test_model_limit_with_filter():
    await User.query.create(name="Test")
    await User.query.create(name="Test")
    await User.query.create(name="Test")

    assert len(await User.query.limit(2).filter(name__iexact="Test").all()) == 2


async def test_model_limit_with_filter_offset():
    await User.query.create(name="Test")
    await User.query.create(name="Test")
    await User.query.create(name="Test")
    result = await User.query.filter(name__icontains="Test").offset(1).limit(2)
    assert len(result) == 2
