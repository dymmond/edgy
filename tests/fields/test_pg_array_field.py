import pytest
import sqlalchemy

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    array = edgy.fields.PGArrayField(sqlalchemy.Integer())
    names = edgy.fields.PGArrayField(sqlalchemy.String(), null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models:
        yield


async def test_model_build():
    user = User(name="Jane", array=[3, 0, 5], names=None)
    assert user.array == [3, 0, 5]
    assert user.names is None
    user = User(name="Jane", array=[3, 0, 5], names=["Jane", "Doe"])
    assert user.array == [3, 0, 5]
    assert user.names == ["Jane", "Doe"]


async def test_model_create():
    user = await User.query.create(name="Jane", array=[3, 0, 5])
    assert user.array == [3, 0, 5]
    assert user.names is None
    await user.save(values={"names": ["Jane", "Doe"]})
    user = await User.query.get()
    assert user.array == [3, 0, 5]
    assert user.names == ["Jane", "Doe"]
