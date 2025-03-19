from typing import Any

import pytest
from pydantic import BaseModel

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, force_rollback=False, drop_database=True)
models = edgy.Registry(database=edgy.Database(database))


class PlainModel(BaseModel):
    first_name: str
    last_name: str
    age: int


class MyModel(edgy.StrictModel):
    ümbedded: dict[str, Any] = edgy.CompositeField(
        inner_fields=[
            ("first_name", edgy.CharField(max_length=255, exclude=True)),
            ("last_name", edgy.CharField(max_length=255, exclude=True, column_name="lname")),
        ],
        prefix_embedded="ämbedded_",
        prefix_column_name="embedded_",
        exclude=False,
        unsafe_json_serialization=True,
    )

    class Meta:
        registry = models


@pytest.fixture()
async def create_test_database():
    async with database:
        await models.create_all()
        async with models.database:
            yield


def test_check():
    assert "ümbedded" in MyModel.meta.fields
    assert "ämbedded_first_name" in MyModel.meta.fields
    assert "ämbedded_last_name" in MyModel.meta.fields
    assert MyModel.table.columns["ämbedded_first_name"].name == "embedded_first_name"
    assert MyModel.table.columns["ämbedded_last_name"].name == "embedded_lname"


async def test_assign(create_test_database):
    obj = await MyModel.query.create(ümbedded={"first_name": "edgy", "last_name": "edgytoo"})
    assert obj.ümbedded["first_name"] == "edgy"
    assert obj.ümbedded["last_name"] == "edgytoo"
    obj.ümbedded = {"first_name": "Santa", "last_name": "Clause"}
    assert obj.ümbedded["first_name"] == "Santa"
    assert obj.ümbedded["last_name"] == "Clause"
    # check if saving object is possible
    await obj.save()


async def test_save(create_test_database):
    obj = await MyModel.query.create(ümbedded={"first_name": "edgy", "last_name": "edgytoo"})
    assert obj.ümbedded["first_name"] == "edgy"
    assert obj.ümbedded["last_name"] == "edgytoo"
    # check if saving object is possible
    await obj.save(values={"ümbedded": {"first_name": "Santa", "last_name": "Clause"}})
    assert obj.ümbedded["first_name"] == "Santa"
    assert obj.ümbedded["last_name"] == "Clause"
