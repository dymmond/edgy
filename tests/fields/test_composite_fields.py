import pytest

import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL
from pydantic import BaseModel

pytestmark = pytest.mark.anyio
database = Database(DATABASE_URL)
models = edgy.Registry(database=database)

class PlainModel(BaseModel):
    first_name: str
    last_name: str
    age: int

class MyModel2(edgy.Model):
    first_name: str = edgy.CharField(max_length=255)
    last_name: str = edgy.CharField(max_length=255, skip_absorption_check=True)
    composite: dict = edgy.CompositeField(inner_fields=["first_name", "last_name"])
    composite2: dict = edgy.CompositeField(inner_fields=[
        ("first_name", edgy.CharField(max_length=255)),
        # should work because of skip_absorption_check
        ("last_name", edgy.IntegerField()),
        ("age", edgy.IntegerField(null=True))
    ], absorb_existing_fields=True)
    plain: PlainModel = edgy.CompositeField(inner_fields=["first_name", "last_name", "age"], model=PlainModel)

    class Meta:
        registry = models


@pytest.fixture()
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture()
async def rollback_connections(create_test_database):
    with database.force_rollback():
        async with database:
            yield


def test_column_type():
    assert edgy.CompositeField(inner_fields=["foo", "fa"]).column_type is None


def test_get_columns_external_fields():
    assert (
        len(edgy.CompositeField(inner_fields=["foo", "fa"]).get_columns("composite")) == 0
    )


def test_get_columns_inner_fields_mixed():
    assert (
        len(edgy.CompositeField(inner_fields=["foo", ("last_name", edgy.CharField(max_length=255))]).get_columns("composite")) == 0
    )


async def test_assign_dict(rollback_connections):
    obj = await MyModel2.query.create(first_name="edgy", last_name="edgytoo")
    assert obj.fields["last_name"].skip_absorption_check == True
    assert obj.composite["first_name"] == "edgy"
    assert obj.composite["last_name"] == "edgytoo"
    assert obj.composite2["age"] is None
    # the composites share fields
    obj.composite2 = {"first_name": "Santa", "last_name": "Clause", "age": 300}
    assert obj.composite["first_name"] == "Santa"
    assert obj.composite["last_name"] == "Clause"
    assert obj.age == 300
    assert obj.first_name == "Santa"
    assert obj.last_name == "Clause"
    assert obj.composite2["age"] == 300
    for key in ["first_name", "last_name", "age"]:
        assert getattr(obj, key) == getattr(obj.plain, key)
    await obj.save()


async def test_assign_obj(rollback_connections):
    obj = await MyModel2.query.create(first_name="edgy", last_name="edgytoo")
    assert obj.fields["last_name"].skip_absorption_check == True
    assert obj.composite["first_name"] == "edgy"
    assert obj.composite["last_name"] == "edgytoo"
    # the composites share fields
    obj.composite2 = MyModel2(first_name="Santa", last_name="Clause", age=300)
    assert obj.composite["first_name"] == "Santa"
    assert obj.composite["last_name"] == "Clause"
    assert obj.age == 300
    assert obj.first_name == "Santa"
    assert obj.last_name == "Clause"
    assert obj.composite2["age"] == 300
    for key in ["first_name", "last_name", "age"]:
        assert getattr(obj, key) == getattr(obj.plain, key)
    await obj.save()
