import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

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


async def test_model_update_or_create():
    user, created = await User.query.update_or_create(
        name="Test", language="English", defaults={"name": "Jane"}
    )
    assert created is True
    assert user.name == "Jane"
    assert user.language == "English"

    user, created = await User.query.update_or_create(
        name="Jane", language="English", defaults={"name": "Test"}
    )
    assert created is False
    assert user.name == "Test"
    assert user.language == "English"
