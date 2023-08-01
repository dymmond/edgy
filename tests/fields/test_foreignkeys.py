import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy import ForeignKey, Model, OneToOne, OneToOneField
from edgy.core.db import fields
from edgy.exceptions import FieldDefinitionError
from edgy.testclient import DatabaseTestClient as Database

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL)
models = edgy.Registry(database=database)


class MyModel(Model):
    name: str = fields.CharField(max_length=255)

    class Meta:
        registry = models


# class AnotherModel(Model):
#     name: str = fields.CharField(max_length=255)
#     my_model: ForeignKey = fields.ForeignKey(MyModel, on_delete=edgy.RESTRICT)

#     class Meta:
#         registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


@pytest.mark.parametrize("model", [ForeignKey, OneToOne, OneToOneField])
def test_can_create_foreign_key(model):
    fk = model(to=MyModel)

    assert fk is not None
    assert fk.to == MyModel


def test_raise_error_on_delete_fk():
    with pytest.raises(FieldDefinitionError):
        ForeignKey(to=MyModel, on_delete=None)


def test_raise_error_on_delete_null():
    with pytest.raises(FieldDefinitionError):
        ForeignKey(to=MyModel, on_delete=edgy.SET_NULL)


def test_raise_error_on_update_null():
    with pytest.raises(FieldDefinitionError):
        ForeignKey(to=MyModel, on_update=edgy.SET_NULL)
