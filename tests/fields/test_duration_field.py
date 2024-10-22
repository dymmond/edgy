from datetime import timedelta

import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    age: timedelta = edgy.fields.DurationField(null=True)

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
async def rollback_transactions():
    async with models.database:
        yield


async def test_model_save():
    user = await User.query.create(name="Jane", age=timedelta(days=365 * 20))

    assert user.age == timedelta(days=365 * 20)
    await user.save()

    user = await User.query.get(pk=user.pk)

    assert user.age == timedelta(days=365 * 20)


async def test_model_save_without():
    user = await User.query.create(name="Jane")

    assert user.age is None
    await user.save()

    user = await User.query.get(pk=user.pk)

    assert user.age is None
