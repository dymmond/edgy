import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class MyModel(edgy.Model):
    first_name: str = edgy.CharField(max_length=255, server_default="edgy")
    last_name: str = edgy.CharField(max_length=255, server_default="edge")

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


async def test_partial_overwrite():
    obj = await MyModel.query.create(first_name="foobar")
    assert obj.first_name == "foobar"
    assert "last_name" not in obj.__dict__
    assert obj.last_name == "edge"
    # lazy load
    assert "last_name" in obj.__dict__


async def test_export_without_load():
    obj = await MyModel.query.create(first_name="foobar")
    assert obj.model_dump(exclude=["id"]) == {
        "first_name": "foobar",
    }


async def test_export_with_implicit_load():
    obj = await MyModel.query.create(first_name="foobar")
    # triggers also implicit load
    assert obj.last_name == "edge"
    assert obj.model_dump(exclude=["id"]) == {"first_name": "foobar", "last_name": "edge"}


async def test_export_with_explicit_load():
    obj = await MyModel.query.create(first_name="foobar")
    await obj.load()
    assert obj.model_dump(exclude=["id"]) == {"first_name": "foobar", "last_name": "edge"}
