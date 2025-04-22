import pytest
import sqlalchemy

import edgy
from edgy.core.db.datastructures import Index
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=255)
    title = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
        indexes = [Index(fields=["name", sqlalchemy.text("LOWER(title)")], name="idx_name_title")]


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
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
