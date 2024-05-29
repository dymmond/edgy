import pytest

import edgy
from edgy.exceptions import QuerySetError
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
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
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_model_values():
    edgy.run_sync(User.query.create(name="John", language="PT", description="A simple description"))
    edgy.run_sync(User.query.create(name="Jane", language="EN", description="Another simple description"))

    users = edgy.run_sync(User.query.values_list())

    assert len(users) == 2

    assert users == [
        (1, "John", "PT", "A simple description"),
        (2, "Jane", "EN", "Another simple description"),
    ]


async def test_model_values_only_with_only():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(User.query.create(name="Jane", language="EN", description="Another simple description"))

    users = edgy.run_sync(User.query.only("name", "language").values_list())
    assert len(users) == 2

    assert users == [(1, "John", "PT"), (2, "Jane", "EN")]


async def test_model_values_list_fields():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(User.query.create(name="Jane", language="EN", description="Another simple description"))

    users = edgy.run_sync(User.query.values_list(["name"]))

    assert len(users) == 2

    assert users == [("John",), ("Jane",)]


async def test_model_values_list_flatten():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(User.query.create(name="Jane", language="EN", description="Another simple description"))

    users = edgy.run_sync(User.query.values_list(["name"], flat=True))

    assert len(users) == 2

    assert users == ["John", "Jane"]


@pytest.mark.parametrize("value", [1, {"name": 1}, (1,), {"edgy"}], ids=["as-int", "as-dict", "as-tuple", "as-set"])
async def test_raise_exception(value):
    with pytest.raises(QuerySetError):
        edgy.run_sync(User.query.values_list(value))


async def test_raise_exception_on_flatten_non_field():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(User.query.create(name="Jane", language="EN", description="Another simple description"))

    users = edgy.run_sync(User.query.values_list(["name"], flat=True))

    assert len(users) == 2

    with pytest.raises(QuerySetError):
        edgy.run_sync(User.query.values_list("age", flat=True))


async def test_model_values_exclude_fields():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(User.query.create(name="Jane", language="EN", description="Another simple description"))

    users = edgy.run_sync(User.query.values_list(exclude=["name", "id"]))
    assert len(users) == 2

    assert users == [("PT", None), ("EN", "Another simple description")]


async def test_model_values_exclude_and_include_fields():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(User.query.create(name="Jane", language="EN", description="Another simple description"))

    users = edgy.run_sync(User.query.values_list(["id"], exclude=["name"]))
    assert len(users) == 2

    assert users == [(1,), (2,)]


async def test_model_values_exclude_none():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(User.query.create(name="Jane", language="EN", description="Another simple description"))

    users = edgy.run_sync(User.query.values_list(exclude_none=True))
    assert len(users) == 2

    assert users == [(1, "John", "PT"), (2, "Jane", "EN", "Another simple description")]


async def test_model_only_with_filter():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(User.query.create(name="Jane", language="EN", description="Another simple description"))

    users = edgy.run_sync(User.query.filter(id=2).values_list("name"))
    assert len(users) == 1

    assert users == [("Jane",)]

    users = edgy.run_sync(User.query.filter(id=3).values_list("name"))

    assert len(users) == 0

    assert users == []
