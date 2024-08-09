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
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_model_group_by():
    await User.query.create(name="Bob")
    await User.query.create(name="Allen")
    await User.query.create(name="Bob")

    users = await User.query.group_by("language", "id").all()
    assert users[0].name == "Bob"
    assert users[1].name == "Allen"

    users = await User.query.group_by("language", "id").all()
    assert users[1].name == "Allen"
    assert users[2].name == "Bob"

    users = await User.query.group_by("id").order_by("id").all()
    assert users[0].name == "Bob"
    assert users[0].id == 1
    assert users[1].name == "Allen"
    assert users[1].id == 2

    users = await User.query.filter(name="Bob").group_by("id").all()
    assert users[0].name == "Bob"
    assert users[0].id == 1
    assert users[1].name == "Bob"
    assert users[1].id == 3

    users = await User.query.group_by("id").limit(1).all()
    assert users[0].name == "Bob"
    assert users[0].id == 1

    users = await User.query.group_by("id").limit(1).offset(1).all()
    assert users[0].name == "Allen"
    assert users[0].id == 2
