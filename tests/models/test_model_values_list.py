import pytest

import edgy
from edgy.exceptions import QuerySetError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    description = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_model_values():
    await User.query.create(name="John", language="PT", description="A simple description")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values_list()

    assert len(users) == 2

    assert users == [
        (1, "John", "PT", "A simple description"),
        (2, "Jane", "EN", "Another simple description"),
    ]


async def test_model_values_only_with_only():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.only("name", "language").values_list()
    assert len(users) == 2

    assert users == [(1, "John", "PT"), (2, "Jane", "EN")]


async def test_model_values_list_fields():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values_list(["name"])

    assert len(users) == 2

    assert users == [("John",), ("Jane",)]


async def test_model_values_list_flatten():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values_list(["name"], flat=True)

    assert len(users) == 2

    assert users == ["John", "Jane"]


@pytest.mark.parametrize("value", [1], ids=["as-int"])
async def test_raise_exception(value):
    with pytest.raises(QuerySetError):
        await User.query.values_list(value)


async def test_raise_exception_on_flatten_non_field():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values_list(["name"], flat=True)

    assert len(users) == 2

    with pytest.raises(QuerySetError):
        await User.query.values_list("age", flat=True)


async def test_model_values_exclude_fields():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values_list(exclude=["name", "id"])
    assert len(users) == 2

    assert users == [("PT", None), ("EN", "Another simple description")]


async def test_model_values_exclude_and_include_fields():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values_list(["id"], exclude=["name"])
    assert len(users) == 2

    assert users == [(1,), (2,)]


async def test_model_values_exclude_none():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values_list(exclude_none=True)
    assert len(users) == 2

    assert users == [(1, "John", "PT"), (2, "Jane", "EN", "Another simple description")]


async def test_model_only_with_filter():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.filter(id=2).values_list("name")
    assert len(users) == 1

    assert users == [("Jane",)]

    users = await User.query.filter(id=3).values_list("name")

    assert len(users) == 0

    assert users == []
