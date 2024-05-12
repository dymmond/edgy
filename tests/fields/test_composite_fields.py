import pytest

import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = Database(DATABASE_URL)
models = edgy.Registry(database=database)


class MyModel2(edgy.Model):
    first_name: str = edgy.CharField(max_length=255)
    last_name: str = edgy.CharField(max_length=255)
    composite: dict = edgy.CompositeField(inner_fields=["first_name", "last_name"])

    class Meta:
        registry = models


@pytest.fixture(autouse=True)
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


def test_column_type():
    assert edgy.CompositeField(inner_fields=["foo"]).column_type is None


def test_get_column():
    assert edgy.CompositeField(inner_fields=["foo"]).get_column("composite") is None


async def test_assign_dict():
    obj = await MyModel2.query.create(first_name="edgy", last_name="edgytoo")
    assert obj.composite["first_name"] == "edgy"
    assert obj.composite["last_name"] == "edgytoo"
    obj.composite = {"first_name": "Santa", "last_name": "Clause"}
    assert obj.composite["first_name"] == "Santa"
    assert obj.composite["last_name"] == "Clause"
    assert obj.first_name == "Santa"
    assert obj.last_name == "Clause"
    await obj.save()


async def test_assign_obj():
    obj = await MyModel2.query.create(first_name="edgy", last_name="edgytoo")
    assert obj.composite["first_name"] == "edgy"
    assert obj.composite["last_name"] == "edgytoo"
    obj.composite = MyModel2(first_name="Santa", last_name="Clause")
    assert obj.composite["first_name"] == "Santa"
    assert obj.composite["last_name"] == "Clause"
    assert obj.first_name == "Santa"
    assert obj.last_name == "Clause"
    await obj.save()
