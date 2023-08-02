import asyncio
import functools
import random
import string

import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.core.db.datastructures import Index
from edgy.testclient import DatabaseTestClient

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)


def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = "".join(random.choice(letters) for i in range(length))
    return result_str


class User(edgy.Model):
    name = edgy.CharField(max_length=255, index=True)
    title = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
        indexes = [Index(fields=["name", "title"], name="idx_name_title")]


class HubUser(edgy.Model):
    name = edgy.CharField(max_length=255)
    title = edgy.CharField(max_length=255, null=True)
    description = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
        indexes = [
            Index(fields=["name", "title"], name="idx_title_name"),
            Index(fields=["name", "description"], name="idx_name_description"),
        ]


class ReflectedUser(edgy.ReflectModel):
    name = edgy.CharField(max_length=255)
    title = edgy.CharField(max_length=255, null=True)
    description = edgy.CharField(max_length=255, null=True)

    class Meta:
        tablename = "hubusers"
        registry = models


class NewReflectedUser(edgy.ReflectModel):
    name = edgy.CharField(max_length=255)
    title = edgy.CharField(max_length=255, null=True)

    class Meta:
        tablename = "hubusers"
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    with database.force_rollback():
        async with database:
            yield


def async_adapter(wrapped_func):
    """
    Decorator used to run async test cases.
    """

    @functools.wraps(wrapped_func)
    def run_sync(*args, **kwargs):
        loop = asyncio.get_event_loop()
        task = wrapped_func(*args, **kwargs)
        return loop.run_until_complete(task)

    return run_sync


async def test_can_reflect_existing_table():
    await HubUser.query.create(name="Test", title="a title", description="desc")

    users = await ReflectedUser.query.all()

    assert len(users) == 1


async def test_can_reflect_existing_table_with_not_all_fields():
    await HubUser.query.create(name="Test", title="a title", description="desc")

    users = await NewReflectedUser.query.all()

    assert len(users) == 1


async def test_can_reflect_existing_table_with_not_all_fields_and_create_record():
    """When a user is created via Reflected model, only the Reflected model fields are passed"""
    await HubUser.query.create(name="Test", title="a title", description="desc")

    users = await NewReflectedUser.query.all()

    assert len(users) == 1

    await NewReflectedUser.query.create(name="Test2", title="A new title", description="lol")

    users = await HubUser.query.all()

    assert len(users) == 2

    user = users[1]

    assert user.name == "Test2"
    assert user.description is None

    users = await NewReflectedUser.query.all()

    assert len(users) == 2

    user = users[1]

    assert user.name == "Test2"
    assert not hasattr(user, "description")


async def test_can_reflect_and_edit_existing_table():
    await HubUser.query.create(name="Test", title="a title", description="desc")

    users = await ReflectedUser.query.all()

    assert len(users) == 1

    user = users[0]

    await user.update(name="edgy", description="updated")

    users = await ReflectedUser.query.all()

    assert len(users) == 1

    user = users[0]

    assert user.name == "edgy"
    assert user.description == "updated"

    users = await HubUser.query.all()

    assert len(users) == 1

    assert user.name == "edgy"
    assert user.description == "updated"
