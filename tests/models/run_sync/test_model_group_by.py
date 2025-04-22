import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

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
    with models.database.force_rollback(True):
        async with models:
            yield


async def test_model_group_by():
    edgy.run_sync(User.query.create(name="Bob"))
    edgy.run_sync(User.query.create(name="Allen"))
    edgy.run_sync(User.query.create(name="Bob"))

    users = edgy.run_sync(User.query.group_by("language", "id").all())
    assert users[0].name == "Bob"
    assert users[1].name == "Allen"

    users = edgy.run_sync(User.query.group_by("language", "id").all())
    assert users[1].name == "Allen"
    assert users[2].name == "Bob"

    users = edgy.run_sync(User.query.group_by("id").order_by("id").all())
    assert users[0].name == "Bob"
    assert users[0].id == 1
    assert users[1].name == "Allen"
    assert users[1].id == 2

    users = edgy.run_sync(User.query.filter(name="Bob").group_by("id").all())
    assert users[0].name == "Bob"
    assert users[0].id == 1
    assert users[1].name == "Bob"
    assert users[1].id == 3

    users = edgy.run_sync(User.query.group_by("id").limit(1).all())
    assert users[0].name == "Bob"
    assert users[0].id == 1

    users = edgy.run_sync(User.query.group_by("id").limit(1).offset(1).all())
    assert users[0].name == "Allen"
    assert users[0].id == 2
