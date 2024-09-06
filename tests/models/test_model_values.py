import pytest

import edgy
from edgy.exceptions import QuerySetError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
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
    await models.drop_all()


@pytest.mark.parametrize(
    "value", [1, {"name": 1}, (1,), {"edgy"}], ids=["as-int", "as-dict", "as-tuple", "as-set"]
)
async def test_raise_exception(value):
    with pytest.raises(QuerySetError):
        await User.query.values(value)


async def test_model_values():
    await User.query.create(name="John", language="PT", description="A simple description")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values()

    assert len(users) == 2

    assert users == [
        {"id": 1, "name": "John", "language": "PT", "description": "A simple description"},
        {"id": 2, "name": "Jane", "language": "EN", "description": "Another simple description"},
    ]


async def test_model_values_only_with_only():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.only("name", "language").values()

    assert len(users) == 2

    assert users == [
        {"id": 1, "name": "John", "language": "PT"},
        {"id": 2, "name": "Jane", "language": "EN"},
    ]


async def test_model_values_list_fields():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values(["name"])

    assert len(users) == 2

    assert users == [{"name": "John"}, {"name": "Jane"}]


async def test_model_values_exclude_fields():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values(exclude=["name", "id"])
    assert len(users) == 2

    assert users == [
        {"language": "PT", "description": None},
        {"language": "EN", "description": "Another simple description"},
    ]


async def test_model_values_exclude_and_include_fields():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values(["id"], exclude=["name"])
    assert len(users) == 2

    assert users == [{"id": 1}, {"id": 2}]


async def test_model_values_exclude_none():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.values(exclude_none=True)
    assert len(users) == 2

    assert users == [
        {"id": 1, "name": "John", "language": "PT"},
        {"id": 2, "name": "Jane", "language": "EN", "description": "Another simple description"},
    ]


async def test_model_only_with_filter():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.filter(id=2).values(["name"])
    assert len(users) == 1

    assert users == [{"name": "Jane"}]

    users = await User.query.filter(id=3).values(["name"])

    assert len(users) == 0

    assert users == []
