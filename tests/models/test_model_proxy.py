from typing import Any

import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    description = edgy.TextField(max_length=5000, null=True)

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


async def test_model_fields_are_different():
    user = await User.query.create(name="John", language="PT", description="John")

    assert user.model_fields["name"].annotation == str
    assert User.model_fields["name"].annotation == str

    assert user.proxy_model.model_fields["name"].annotation == Any
    assert User.proxy_model.model_fields["name"].annotation == Any
