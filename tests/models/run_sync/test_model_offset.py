import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
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
    async with database:
        await models.create_all()
        yield
    await models.drop_all()


async def test_offset():
    edgy.run_sync(User.query.create(name="Test"))
    edgy.run_sync(User.query.create(name="Jane"))

    users = edgy.run_sync(User.query.offset(1).limit(1).all())
    assert users[0].name == "Jane"
