import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_ALTERNATIVE_URL, DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
another_db = DatabaseTestClient(DATABASE_ALTERNATIVE_URL)

registry = edgy.Registry(database=database, extra={"alternative": another_db})
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

    with another_db.force_rollback():
        async with another_db:
            yield


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = registry


def test_has_multiple_connections():
    assert "alternative" in User.meta.registry.extra
