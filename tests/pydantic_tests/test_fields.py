import pytest

import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100)
    name_short: str = edgy.CharField(max_length=2, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100)
    rating: int = edgy.IntegerField(minimum=1, maximum=5)
    in_stock: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models
        name = "products"


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


async def test_raise_error_on_max_length_field():
    await User.query.create(name="Test")
    users = await User.query.all()

    assert len(users) == 1

    with pytest.raises(ValueError):
        await User.query.create(name="Edgy", name_short="edgy")


async def test_raise_error_on_missing_required_field():
    with pytest.raises(ValueError):
        await User.query.create()
