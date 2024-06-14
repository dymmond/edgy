from typing import ClassVar

import pytest

import edgy
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
    model1: ClassVar[InheritableModel] = InheritableModel
    model2: ClassVar[NonInheritableModel] = NonInheritableModel

    class Meta:
        registry = models

class MyModel2(MyModel1):
    model3: ClassVar[MyModel1] = MyModel1
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
    assert "model1" in MyModel1.meta.fields_mapping
    assert "model1_first_name" in MyModel1.meta.fields_mapping
    # prefixed _ is removed
    assert "model1_last_name" in MyModel1.meta.fields_mapping
    assert "model2" in MyModel1.meta.fields_mapping
    assert "model2_first_name" in MyModel1.meta.fields_mapping

    assert "model1" in MyModel2.meta.fields_mapping
    assert "model2" not in MyModel2.meta.fields_mapping
    assert "model3" in MyModel2.meta.fields_mapping
    assert "model1_first_name" in MyModel2.meta.fields_mapping
    assert "model2_first_name" not in MyModel2.meta.fields_mapping
    assert "model3_first_name" not in MyModel2.meta.fields_mapping
    assert "model3_model1_first_name" in MyModel2.meta.fields_mapping
    assert isinstance(MyModel2.meta.fields_mapping["model3_model1_last_name"], edgy.ExcludeField)


async def test_fields_db(rollback_connections):
    model1_def = {
        "model1_first_name": "edgy",
        "model1_last_name":"edgytoo",
        "model2_first_name": "edgy",
        "model2_last_name": "edgytoo",
    }
    obj = await MyModel1.query.create(
        **model1_def
    )
    assert obj.model_dump() == {
        "model1": {
            "first_name": "edgy",
            "last_name": "edgytoo",
        },
        "model2": {
            "first_name": "edgy",
            "last_name": "edgytoo",
        }
    }
    model2_def = {
        "model1": {
            "first_name": "edgy",
            "last_name": "edgytoo",
        },
        "model3": {
            "model1_first_name": "edgy",
            "model2_last_name": "edgy",
        }
    }


    # TODO: fix failure for embedded Composite
    # stub for preventing mypy to complain
    assert model2_def == model2_def

    #obj2 = await MyModel2.query.create(**model2_def)

    #assert obj.model_dump() == {
    #    "model1": {
    #        "first_name": "edgy",
    #        "last_name": "ed2gytoo",
    #    },
    #    "model3": {
    #        "first_name": "edgy",
    #    }
    #}
