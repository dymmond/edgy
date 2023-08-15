import random

import pytest
from tests.settings import DATABASE_ALTERNATIVE_URL, DATABASE_URL

import edgy
from edgy.exceptions import ImproperlyConfigured
from edgy.testclient import DatabaseTestClient as Database


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


database = Database(url=DATABASE_URL)
another_db = Database(url=DATABASE_ALTERNATIVE_URL)

registry = edgy.Registry(database=database)
another_registry = edgy.Registry(database=another_db)
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
async def rollback_connections():
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
        registries = {"alternative": another_registry}


class BaseModel(edgy.Model):
    name: str = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = registry
        registries = {"alternative": another_registry}


class Product(BaseModel):
    ...


class Item(BaseModel):
    class Meta:
        registries = {"another": another_registry}


def test_raise_exception_main():
    with pytest.raises(ImproperlyConfigured):

        class Nother(edgy.Model):
            class Meta:
                registry = registry
                registries = [another_registry]
