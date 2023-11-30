import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.core.db.querysets.clauses import and_
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    email = edgy.EmailField(null=True, max_length=255)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_filter_with_and():
    user = await User.query.create(name="Adam", language="EN")

    results = await User.query.filter(and_(User.columns.name == "Adam"))

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_filter_with_and_two():
    await User.query.create(name="Adam")
    await User.query.create(name="Edgy")

    results = await User.query.filter(
        and_(User.columns.name == "Adam", User.columns.name == "Edgy")
    )

    assert len(results) == 0


async def test_filter_with_and_three():
    await User.query.create(name="Adam")
    user = await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.filter(
        and_(User.columns.name == user.name, User.columns.email == user.email)
    )

    assert len(results) == 1


async def test_filter_with_and_four():
    await User.query.create(name="Adam")
    user = await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.filter(and_(User.columns.name == user.name)).filter(
        and_(User.columns.email == user.email)
    )
    assert len(results) == 1


async def test_filter_with_contains():
    await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.filter(and_(User.columns.email.contains("edgy")))
    assert len(results) == 2
