from contextlib import redirect_stdout
from io import StringIO

import pytest

import edgy
from edgy.core.db.datastructures import Index
from edgy.testclient import DatabaseTestClient
from edgy.utils.inspect import InspectDB
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database)
second = edgy.Registry(database=edgy.Database(database, force_rollback=False))

expected_result1 = """
class Users(edgy.ReflectModel):
    name = edgy.CharField(max_length=255, null=False)
    title = edgy.CharField(max_length=255, null=True)
    id = edgy.BigIntegerField(autoincrement=True, null=False, primary_key=True)

    class Meta:
        registry = registry
        tablename = "users"
""".strip()

expected_result2 = """
class Hubusers(edgy.ReflectModel):
    name = edgy.CharField(max_length=255, null=False)
    title = edgy.CharField(max_length=255, null=True)
    description = edgy.CharField(max_length=255, null=True)
    id = edgy.BigIntegerField(autoincrement=True, null=False, primary_key=True)

    class Meta:
        registry = registry
        tablename = "hubusers"
""".strip()


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=255, index=True)
    title = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
        indexes = [Index(fields=["name", "title"], name="idx_name_title")]


class HubUser(edgy.StrictModel):
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
        registry = second


class NewReflectedUser(edgy.ReflectModel):
    name = edgy.CharField(max_length=255)
    title = edgy.CharField(max_length=255, null=True)

    class Meta:
        tablename = "hubusers"
        registry = second


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with models:
        await models.create_all()
        async with second:
            yield
        if not database.drop:
            await models.drop_all()


async def test_can_reflect_existing_table():
    await HubUser.query.create(name="Test", title="a title", description="desc")

    users = await ReflectedUser.query.all()

    assert len(users) == 1


async def test_can_defer_loading():
    await HubUser.query.create(name="Test", title="a title", description="desc")

    user = await ReflectedUser.query.defer("description").get()

    assert "description" not in user.__dict__
    assert user.description == "desc"
    assert "description" in user.__dict__


async def test_can_reflect_existing_table_with_not_all_fields():
    await HubUser.query.create(name="Test", title="a title", description="desc")

    users = await NewReflectedUser.query.all()

    assert len(users) == 1


async def test_can_reflect_existing_table_with_not_all_fields_and_create_record():
    """When a user is created via Reflected model, only the Reflected model fields are passed"""
    await HubUser.query.create(name="Test", title="a title", description="desc")

    users = await NewReflectedUser.query.all()

    assert len(users) == 1

    # description is not a field and won't be serialized
    await NewReflectedUser.query.create(name="Test2", title="A new title", description="lol")

    users = await HubUser.query.all()

    assert len(users) == 2

    user = users[1]

    assert user.name == "Test2"
    # not a reflected field so kept unset
    assert user.description is None


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


async def test_create_correct_inspect_db():
    inflected = InspectDB(str(models.database.url))
    out = StringIO()
    with redirect_stdout(out):
        inflected.inspect()
    out.seek(0)
    generated = out.read()
    # indexes are not sorted and appear in any order so they are removed
    assert expected_result1 in generated
    assert expected_result2 in generated
