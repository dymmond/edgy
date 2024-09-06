import random

import pytest

import edgy
from edgy.exceptions import SchemaError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL


def get_random_string(
    length: int = 12,
    allowed_chars: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
) -> str:
    """
    Returns a securely generated random string.
    The default length of 12 with the a-z, A-Z, 0-9 character set returns
    a 71-bit value. log_2((26+26+10)^12) =~ 71 bits
    """
    return "".join(random.choice(allowed_chars) for _ in range(length))


database = DatabaseTestClient(DATABASE_URL)
registry = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    try:
        await registry.create_all()
        yield
        await registry.drop_all()
    except Exception:
        pytest.skip("No database available")


@pytest.fixture(autouse=True)
async def rollback_transactions():
    with database.force_rollback():
        async with database:
            yield


@pytest.mark.parametrize("schema", ["edgy", "saffier", "esmerald", "tenant"])
async def test_create_schema(schema):
    # Get rid of the schema
    await registry.schema.drop_schema(schema=schema, cascade=True, if_exists=True)

    await registry.schema.create_schema(schema=schema, if_not_exists=False)


@pytest.mark.skipif(database.url.dialect != "postgresql", reason="Testing for postgres")
async def test_raises_schema_error_if_exists():
    schema = get_random_string(5)
    await registry.schema.create_schema(schema=schema, if_not_exists=False)

    with pytest.raises(SchemaError) as raised:
        await registry.schema.create_schema(schema=schema, if_not_exists=False)

    assert (
        raised.value.args[0]
        == f"<class 'asyncpg.exceptions.DuplicateSchemaError'>: schema \"{schema}\" already exists"
    )


async def test_can_drop_schema():
    schema = get_random_string(5)
    await registry.schema.create_schema(schema=schema, if_not_exists=False)
    await registry.schema.drop_schema(schema=schema, cascade=True)


@pytest.mark.parametrize(
    "schema",
    [get_random_string(5), get_random_string(7), get_random_string(8), get_random_string(6)],
)
async def test_drop_schemas(schema):
    await registry.schema.create_schema(schema=schema, if_not_exists=False)
    await registry.schema.drop_schema(schema=schema, cascade=True)


async def test_cannot_drop_not_existing_schema():
    schema = get_random_string(5)
    await registry.schema.create_schema(schema=schema, if_not_exists=False)
    await registry.schema.drop_schema(schema=schema, cascade=True)

    with pytest.raises(SchemaError) as raised:
        await registry.schema.drop_schema(schema=schema, cascade=True)

    assert (
        raised.value.args[0]
        == f"<class 'asyncpg.exceptions.InvalidSchemaNameError'>: schema \"{schema}\" does not exist"
    )
