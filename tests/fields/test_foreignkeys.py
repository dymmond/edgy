import pytest

import edgy
from edgy import ForeignKey, Model, OneToOne, OneToOneField
from edgy.core.db import fields
from edgy.exceptions import FieldDefinitionError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


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
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
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
