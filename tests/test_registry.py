import pytest
from asyncpg.exceptions import DuplicateSchemaError, InvalidSchemaNameError
from tests.settings import DATABASE_URL

import edgy
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
registry = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    try:
        await registry.create_all()
        yield
        await registry.drop_all()
    except Exception:
        pytest.skip("No database available")


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


@pytest.mark.parametrize("schema", ["edgy", "saffier", "esmerald", "tenant"])
async def test_create_schema(schema):
    await registry.create_schema(schema=schema, if_not_exists=False)


@pytest.mark.skipif(database.url.dialect != "postgresql", reason="Testing for postgres")
async def test_raises_schema_error_if_exists():
    await registry.create_schema(schema="edgy", if_not_exists=False)

    with pytest.raises(DuplicateSchemaError) as raised:
        await registry.create_schema(schema="edgy", if_not_exists=False)

    assert raised.value.args[0] == 'schema "edgy" already exists'


async def test_can_drop_schema():
    await registry.create_schema(schema="edgy", if_not_exists=False)
    await registry.drop_schema(schema="edgy", cascade=True)


@pytest.mark.parametrize("schema", ["edgy", "saffier", "esmerald", "tenant"])
async def test_drop_schemas(schema):
    await registry.create_schema(schema=schema, if_not_exists=False)
    await registry.drop_schema(schema=schema, cascade=True)


async def test_cannot_drop_not_existing_schema():
    await registry.create_schema(schema="edgy", if_not_exists=False)
    await registry.drop_schema(schema="edgy", cascade=True)

    with pytest.raises(InvalidSchemaNameError) as raised:
        await registry.drop_schema(schema="edgy", cascade=True)

    assert raised.value.args[0] == 'schema "edgy" does not exist'
