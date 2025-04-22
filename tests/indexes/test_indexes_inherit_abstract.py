import random
import string

import pytest

import edgy
from edgy.core.db.datastructures import Index
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = "".join(random.choice(letters) for i in range(length))
    return result_str


class BaseUserAbstract(edgy.Model):
    name = edgy.CharField(max_length=255, index=True)
    title = edgy.CharField(max_length=255, null=True)

    class Meta:
        abstract = True
        indexes = [Index(fields=["name", "title"], name="idx_name_title")]


class User(BaseUserAbstract):
    class Meta:
        registry = models


class AbsHubUser(edgy.Model):
    name = edgy.CharField(max_length=255)
    title = edgy.CharField(max_length=255, null=True)
    description = edgy.CharField(max_length=255, null=True)

    class Meta:
        abstract = True
        indexes = [
            Index(fields=["name", "title"], name="idx_title_name"),
            Index(fields=["name", "description"], name="idx_name_description"),
        ]


class HubUser(AbsHubUser):
    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


async def test_creates_index_for_table():
    await User.query.create(name="Test", title="a title")

    indexes = {value.name for value in User.table.indexes}

    assert "idx_name_title" in indexes


async def test_creates_multiple_index_for_table():
    await HubUser.query.create(name="Test", title="a title")

    indexes = {value.name for value in HubUser.table.indexes}

    assert "idx_name_description" in indexes
