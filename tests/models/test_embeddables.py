from typing import ClassVar

import pytest

import edgy
from edgy.core.db.fields.base import BaseField
from edgy.core.db.models.managers import BaseManager
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = Database(DATABASE_URL)
models = edgy.Registry(database=database)


class InheritableModel(edgy.Model):
    first_name: str = edgy.CharField(max_length=255)
    last_name: str = edgy.CharField(max_length=255)

    class Meta:
        abstract = True


class NonInheritableModel(InheritableModel):
    class Meta:
        abstract = True
        inherit = False


class MyModel1(edgy.Model):
    id = edgy.IntegerField(primary_key=True, autoincrement=True, inherit=False, exclude=True)
    model1: ClassVar[InheritableModel] = InheritableModel
    model2 = NonInheritableModel

    class Meta:
        registry = models


class MyModel2(MyModel1):
    id2 = edgy.IntegerField(primary_key=True, autoincrement=True, inherit=False, exclude=True)
    model3: ClassVar[MyModel1] = MyModel1
    # because of exluding and inheritance we cannot use model3 anymore
    model3_model1_last_name = edgy.ExcludeField()


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


def test_fields():
    assert "id" in MyModel1.meta.fields
    assert "id2" not in MyModel1.meta.fields
    assert "id" in MyModel1.pkcolumns
    assert "id2" not in MyModel1.pkcolumns
    assert "model1" in MyModel1.meta.fields
    assert "model1_first_name" in MyModel1.meta.fields
    # prefixed _ is removed
    assert "model1_last_name" in MyModel1.meta.fields
    assert "model2" in MyModel1.meta.fields
    assert "model2_first_name" in MyModel1.meta.fields

    assert "id2" in MyModel2.meta.fields
    assert "id" not in MyModel2.meta.fields
    assert "id2" in MyModel2.pkcolumns
    assert "id" not in MyModel2.pkcolumns
    assert "model1" in MyModel2.meta.fields
    assert "model2" not in MyModel2.meta.fields
    assert "model3" in MyModel2.meta.fields
    assert "model1_first_name" in MyModel2.meta.fields
    assert "model2_first_name" not in MyModel2.meta.fields
    assert "model3_first_name" not in MyModel2.meta.fields
    assert "model3_model1_first_name" in MyModel2.meta.fields
    assert isinstance(MyModel2.meta.fields["model3_model1_last_name"], edgy.ExcludeField)


@pytest.mark.parametrize(
    "model",
    [MyModel1, MyModel2],
)
def test_field_types(model):
    for field in model.meta.fields.values():
        assert not isinstance(field, BaseManager)
    for field in model.meta.fields.values():
        assert isinstance(field, BaseField)
    for manager in model.meta.managers.values():
        assert isinstance(manager, BaseManager)


@pytest.mark.parametrize(
    "model",
    [MyModel1, MyModel2],
)
def test_field_names(model):
    for field_name, field in model.meta.fields.items():
        assert field_name == field.name


async def test_fields_db(rollback_connections):
    model1_def = {
        "model1_first_name": "edgy",
        "model1_last_name": "edgytoo",
        "model2_first_name": "edgy",
        "model2_last_name": "edgytoo",
    }
    obj = await MyModel1.query.create(**model1_def)
    assert obj.model_dump() == {
        "model1": {
            "first_name": "edgy",
            "last_name": "edgytoo",
        },
        "model2": {
            "first_name": "edgy",
            "last_name": "edgytoo",
        },
    }
    model2_def = {
        "model1": {
            "first_name": "edgy",
            "last_name": "edgytoo",
        },
        "model3": {
            "model1": {
                "first_name": "edgy",
                "last_name": "edgytoo",
            },
        },
    }

    obj2 = await MyModel2.query.create(**model2_def)

    # dumping model3 is broken because some fields are missing for Constructors
    assert obj2.model_dump(include={"model1": True}) == {"model1": model2_def["model1"]}
    for key, val in (
        ("model1_first_name", "edgy"),
        ("model1_last_name", "edgytoo"),
        ("model3_model1_first_name", "edgy"),
    ):
        assert getattr(obj2, key) == val
    with pytest.raises(AttributeError):
        obj2.model3_model2_first_name  # noqa
