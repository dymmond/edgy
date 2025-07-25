from typing import Any

import pytest
from pydantic import BaseModel

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
models = edgy.Registry(
    database=DatabaseTestClient(DATABASE_URL, force_rollback=False, drop_database=True)
)


class PlainModel(BaseModel):
    first_name: str
    last_name: str
    age: int


class MyModel2(edgy.StrictModel):
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


class MyModelEmbedded(edgy.StrictModel):
    first_name: str = edgy.CharField(max_length=255)
    last_name: str = edgy.CharField(max_length=255, skip_absorption_check=True)
    embedded: dict[str, Any] = edgy.CompositeField(
        inner_fields=[
            ("first_name", edgy.CharField(max_length=255, exclude=True)),
            ("last_name", edgy.CharField(max_length=255, exclude=True)),
        ],
        prefix_embedded="embedded_",
        exclude=False,
    )

    class Meta:
        registry = models


class MyModelEmbedded2(edgy.StrictModel):
    first_name: str = edgy.CharField(max_length=255)
    last_name: str = edgy.CharField(max_length=255, skip_absorption_check=True)
    embedded: dict[str, Any] = edgy.CompositeField(
        inner_fields=[
            ("first_name", edgy.CharField(max_length=255, exclude=True)),
            ("last_name", edgy.CharField(max_length=255, exclude=True)),
        ],
        prefix_embedded="embedded_",
        exclude=False,
        unsafe_json_serialization=True,
    )

    class Meta:
        registry = models


@pytest.fixture()
async def create_test_database():
    async with models:
        await models.create_all()
        yield


def test_column_type():
    assert edgy.CompositeField(inner_fields=["foo", "fa"]).column_type is None


def test_get_columns_external_fields():
    assert len(edgy.CompositeField(inner_fields=["foo", "fa"]).get_columns("composite")) == 0


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
async def test_assign(create_test_database, assign_object):
    obj = await MyModel2.query.create(first_name="edgy", last_name="edgytoo")
    assert obj.meta.fields["last_name"].skip_absorption_check is True
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
async def test_assign_embedded(create_test_database, assign_object):
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
    assert obj.meta.fields["embedded_first_name"].exclude
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


def test_dump_composite_dict_json():
    obj1 = MyModelEmbedded(
        first_name="edgy",
        last_name="edgytoo",
        embedded_first_name="edgy2embedded",
        embedded_last_name="edgytoo2embedded",
    )
    obj2 = MyModelEmbedded2(
        first_name="edgy",
        last_name="edgytoo",
        embedded_first_name="edgy2embedded",
        embedded_last_name="edgytoo2embedded",
    )
    assert "embedded" not in obj1.model_dump(mode="json")
    assert "embedded" in obj2.model_dump(mode="json")
    assert obj1.model_dump(mode="json", exclude=("embedded",)) == obj2.model_dump(
        mode="json", exclude=("embedded",)
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
    assert obj.model_dump(exclude={"age": True}, include=("first_name", "last_name", "age")) == {
        "first_name": "edgy",
        "last_name": "edgytoo",
    }


def test_inheritance():
    class AbstractModel(edgy.StrictModel):
        composite_inherit: dict[str, Any] = edgy.CompositeField(
            inner_fields=[
                ("first_name", edgy.CharField(max_length=255)),
                ("last_name", edgy.CharField(max_length=255)),
                ("age", edgy.IntegerField(null=True)),
            ],
        )

        class Meta:
            abstract = True

    assert all(field.owner is AbstractModel for field in AbstractModel.meta.fields.values())

    class ConcreteModel1(AbstractModel):
        composite_inherit: dict[str, Any] = edgy.CompositeField(
            inner_fields=[
                ("first_name", edgy.CharField(max_length=255)),
                ("last_name", edgy.CharField(max_length=51)),
            ],
        )

    assert "age" not in ConcreteModel1.meta.fields
    assert ConcreteModel1.meta.fields["last_name"].max_length == 51
    assert all(field.owner is ConcreteModel1 for field in ConcreteModel1.meta.fields.values())

    class ConcreteModel2(AbstractModel):
        composite_absorb: dict[str, Any] = edgy.CompositeField(
            inner_fields=[
                ("first_name", edgy.CharField(max_length=255)),
                ("last_name", edgy.CharField(max_length=50)),
            ],
            absorb_existing_fields=True,
        )

    assert "age" in ConcreteModel2.meta.fields
    assert ConcreteModel2.meta.fields["last_name"].max_length == 255
    assert all(field.owner is ConcreteModel2 for field in ConcreteModel2.meta.fields.values())

    class ConcreteModel3(AbstractModel):
        composite_overwrite: dict[str, Any] = edgy.CompositeField(
            inner_fields=[
                ("first_name", edgy.CharField(max_length=255)),
                ("last_name", edgy.CharField(max_length=50)),
            ],
        )

    assert ConcreteModel3.meta.fields["last_name"].max_length == 50
    assert "age" in ConcreteModel3.meta.fields


def test_copying_of_inner_fields():
    field = edgy.CompositeField(
        inner_fields=[
            ("first_name", edgy.CharField(max_length=255)),
            ("last_name", edgy.CharField(max_length=255)),
        ],
    )
    fields = field.get_embedded_fields("field", {})
    assert fields["first_name"].owner is None
    fields["first_name"].owner = "test"
    fields["first_name"].newattribute = "test"
    fields2 = field.get_embedded_fields("field", {})
    assert fields2["first_name"].owner is None
    assert not hasattr(fields2["first_name"], "newattribute")


def test_copying_of_inner_fields_nested():
    inner_field = edgy.CompositeField(
        inner_fields=[
            ("first_name", edgy.CharField(max_length=255)),
            ("last_name", edgy.CharField(max_length=255)),
        ],
    )
    outer_field = edgy.CompositeField(inner_fields=[("inner", inner_field)])
    fields = outer_field.get_embedded_fields("outer_field", {})["inner"].get_embedded_fields(
        "inner_field", {}
    )
    assert fields["first_name"].owner is None
    fields["first_name"].owner = "test"
    fields["first_name"].newattribute = "test"
    fields2 = outer_field.get_embedded_fields("outer_field", {})["inner"].get_embedded_fields(
        "inner_field", {}
    )
    assert fields2["first_name"].owner is None
    assert not hasattr(fields2["first_name"], "newattribute")
