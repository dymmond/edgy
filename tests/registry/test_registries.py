import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_ALTERNATIVE_URL, DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
another_db = DatabaseTestClient(DATABASE_ALTERNATIVE_URL, drop_database=True)

registry = edgy.Registry(
    database=edgy.Database(database, force_rollback=True),
    extra={"alternative": another_db},
)
pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database, another_db:
        await registry.create_all(databases=(None, "alternative"))
        yield
        if not database.drop:
            await registry.drop_all(databases=(None, "alternative"))


@pytest.fixture(autouse=True)
async def rollback_transactions():
    async with registry:
        yield


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = registry


async def test_has_multiple_connections():
    assert "alternative" in User.meta.registry.extra


async def test_user_on_both():
    assert await User.query.count() == 0
    assert await User.query.using(database="alternative").count() == 0


async def test_copy_registry():
    _copy = registry.__copy__()
    assert "User" in _copy.models and len(_copy.models) == 1
    assert all(x.meta.registry is _copy for x in _copy.models.values())
    assert all(x.owner is _copy.models["User"] for x in _copy.models["User"].meta.fields.values())
