import pytest

import edgy
from edgy.core.db.querysets.clauses import not_
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    email = edgy.EmailField(null=True, max_length=255)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


async def test_filter_with_not():
    await User.query.create(name="Adam", language="EN")

    results = await User.query.filter(not_(User.columns.name == "Adam"))

    assert len(results) == 0


async def test_filter_with_not_two():
    await User.query.create(name="Adam")
    await User.query.create(name="Edgy")
    user = await User.query.create(name="Esmerald")

    results = await User.query.filter(not_(User.columns.name == "Edgy")).filter(
        not_(User.columns.name == "Adam")
    )

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_filter_with_not_style():
    await User.query.create(name="Adam")
    await User.query.create(name="Edgy")
    user = await User.query.create(name="Esmerald")

    results = await User.query.not_(name="Edgy").not_(name="Adam")

    assert len(results) == 1
    assert results[0].pk == user.pk
