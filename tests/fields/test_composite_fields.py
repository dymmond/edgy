from typing import Any, Dict

import pytest
from pydantic import BaseModel

import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

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
    composite2: dict = edgy.CompositeField(
        inner_fields=[
            ("first_name", edgy.CharField(max_length=255)),
            # should work because of skip_absorption_check
            ("last_name", edgy.IntegerField()),
            ("age", edgy.IntegerField(null=True)),
        ],
        absorb_existing_fields=True,
    )
    plain: PlainModel = edgy.CompositeField(
        inner_fields=["first_name", "last_name", "age"], model=PlainModel
    )

    class Meta:
        registry = models


class EmbeddedModel(BaseModel):
    first_name: str
    last_name: str


class MyModelEmbedded(edgy.Model):
    first_name: str = edgy.CharField(max_length=255)
    last_name: str = edgy.CharField(max_length=255, skip_absorption_check=True)
    embedded: Dict[str, Any] = edgy.CompositeField(
        inner_fields=[
            ("first_name", edgy.CharField(max_length=255, exclude=True)),
            ("last_name", edgy.CharField(max_length=255, exclude=True)),
        ],
        prefix_embedded="embedded_",
        exclude=False,
    )

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
        len(edgy.CompositeField(inner_fields=["foo", "fa"]).get_columns("composite"))
        == 0
    )


def test_get_columns_inner_fields_mixed():
    assert (
        len(
            edgy.CompositeField(
                inner_fields=["foo", ("last_name", edgy.CharField(max_length=255))]
            ).get_columns("composite")
        )
        == 0
    )


@pytest.mark.parametrize(
    "assign_object",
    [
        {"first_name": "Santa", "last_name": "Clause", "age": 300},
        MyModel2(first_name="Santa", last_name="Clause", age=300),
    ],
)
async def test_assign(rollback_connections, assign_object):
    obj = await MyModel2.query.create(first_name="edgy", last_name="edgytoo")
    assert obj.fields["last_name"].skip_absorption_check is True
    assert obj.composite["first_name"] == "edgy"
    assert obj.composite["last_name"] == "edgytoo"
    assert obj.composite2["age"] is None
    # the composites share fields
    obj.composite2 = assign_object
    assert obj.composite["first_name"] == "Santa"
    assert obj.composite["last_name"] == "Clause"
    assert obj.age == 300
    assert obj.first_name == "Santa"
    assert obj.last_name == "Clause"
    assert obj.composite2["age"] == 300
    for key in ["first_name", "last_name", "age"]:
        assert getattr(obj, key) == getattr(obj.plain, key)
    # check if saving object is possible
    await obj.save()


# the age argument just should be ignored
@pytest.mark.parametrize(
    "assign_object",
    [
        {"first_name": "Santa", "last_name": "Clause", "age": 300},
        MyModel2(first_name="Santa", last_name="Clause", age=300),
    ],
)
async def test_assign_embedded(rollback_connections, assign_object):
    obj = await MyModelEmbedded.query.create(
        first_name="edgy",
        last_name="edgytoo",
        embedded_first_name="edgy2embedded",
        embedded_last_name="edgytoo2embedded",
    )
    assert obj.first_name == "edgy"
    assert obj.last_name == "edgytoo"
    assert obj.embedded["first_name"] == "edgy2embedded"
    assert obj.embedded["last_name"] == "edgytoo2embedded"
    # the composites share fields
    obj.embedded = assign_object
    assert obj.embedded["first_name"] == "Santa"
    assert obj.embedded["last_name"] == "Clause"
    assert obj.first_name == "edgy"
    assert obj.last_name == "edgytoo"
    # check if saving object is possible
    await obj.save()


def test_dump_composite_dict():
    obj = MyModelEmbedded(
        first_name="edgy",
        last_name="edgytoo",
        embedded_first_name="edgy2embedded",
        embedded_last_name="edgytoo2embedded",
    )
    assert obj.fields["embedded_first_name"].exclude
    assert obj.model_dump() == {
        "first_name": "edgy",
        "last_name": "edgytoo",
        "embedded": {
            "first_name": "edgy2embedded",
            "last_name": "edgytoo2embedded",
        },
    }
    assert obj.model_dump(exclude=("embedded",)) == {
        "first_name": "edgy",
        "last_name": "edgytoo",
    }

    # we cannot filter the dict
    with pytest.raises(AssertionError):
        obj.model_dump(
            exclude={
                "embedded": "first_name",
            }
        )
    with pytest.raises(AssertionError):
        obj.model_dump(
            include={
                "embedded": "first_name",
            }
        )


def test_dump_composite_model():
    obj = MyModel2(first_name="edgy", last_name="edgytoo", age=100)
    assert obj.model_dump(include={"plain": {"first_name": True}}) == {
        "plain": {
            "first_name": "edgy",
        },
    }
    assert obj.model_dump(
        exclude={"plain": {"first_name": True, "age": True}}, include=("plain",)
    ) == {
        "plain": {
            "last_name": "edgytoo",
        },
    }
    # now we stress test with both
    assert obj.model_dump(
        exclude={"age": True}, include=("first_name", "last_name", "age")
    ) == {"first_name": "edgy", "last_name": "edgytoo"}
