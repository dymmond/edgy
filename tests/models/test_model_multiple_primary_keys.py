import pytest

import edgy
from edgy import Registry
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = Registry(database=database)
nother = Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    non_default_id = edgy.BigIntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100, primary_key=True)
    language = edgy.CharField(max_length=200, null=True)
    parent = edgy.ForeignKey("User", on_delete=edgy.SET_NULL, null=True)

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


async def test_model_multiple_primary_key():
    user = await User.query.create(language="EN", name="edgy")

    assert user.non_default_id == 1
    assert user.name == "edgy"
    assert user.pk["non_default_id"] == 1
    assert user.pk["name"] == "edgy"
    users = await User.query.filter()
    assert len(users) == 1

    user2 = await User.query.create(language="DE", name="edgy2", parent=user)
    assert user2.name == "edgy2"
    assert user2.pk["non_default_id"] == 2
    assert user2.pk["name"] == "edgy2"
    assert user2.parent.pk["non_default_id"] == 1
    users = await User.query.filter()
    assert len(users) == 2


async def test_model_multiple_primary_key_explicit_id():
    user = await User.query.create(language="EN", name="edgy", non_default_id=45)

    assert user.non_default_id == 45
    assert user.name == "edgy"
    assert user.pk["non_default_id"] == 45
    assert user.pk["name"] == "edgy"
    users = await User.query.filter()
    assert len(users) == 1

    user2 = await User.query.create(language="DE", name="edgy2", parent=user)
    assert user2.name == "edgy2"
    assert user2.pk["name"] == "edgy2"
    assert user2.parent.pk["non_default_id"] == 45
    users = await User.query.filter()
    assert len(users) == 2


async def test_model_multiple_primary_key_idempotence():
    user = await User.query.create(language="EN", name="edgy")
    user2 = await User.query.create(language="EN", name="edgy2", parent=user)
    extracted_fields = user2.extract_db_fields()
    column_values = user2.extract_column_values(extracted_fields)
    assert User(**column_values).model_dump() == user2.model_dump(
        exclude={"parent": {"language": True}}
    )
