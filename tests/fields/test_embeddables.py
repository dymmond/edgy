from typing import Any, Dict, ClassVar

import pytest
from pydantic import BaseModel

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
    pass


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
    assert "model2" in MyModel1.meta.fields_mapping

    assert "model1" in MyModel2.meta.fields_mapping
    assert "model2" not in MyModel2.meta.fields_mapping
