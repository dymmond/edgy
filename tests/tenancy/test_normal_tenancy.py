from uuid import uuid4

import pytest

import edgy
from edgy.core.tenancy.utils import create_schema
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = edgy.Database(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class Item(edgy.StrictModel):
    sku: edgy.CharField = edgy.UUIDField(default=uuid4)
    name: edgy.CharField = edgy.CharField(max_length=255)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        # we have a normal database object here
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models:
        yield


async def test_can_create_tenant_records():
    # Create the tenant
    # using the defaults from Edgy.
    await create_schema(
        registry=models, schema_name="esmerald", if_not_exists=True, should_create_tables=True
    )

    for i in range(10):
        await Item.query.create(name=f"item-{i}")

    for i in range(5):
        await Item.query.using(schema="esmerald").create(name=f"item-schema-{i}")

    total = await Item.query.count()

    assert total == 10

    total_schema = await Item.query.using(schema="esmerald").count()

    assert total_schema == 5
