from typing import Any

import pytest

import edgy
from edgy.core.marshalls import Marshall, fields
from edgy.core.marshalls.config import ConfigMarshall
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_connections():
    async with models:
        yield


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100, null=True)
    email: str = edgy.EmailField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models

    def get_name(self) -> str:
        return f"Details about {self.name}"


class UserMarshall(Marshall):
    marshall_config = ConfigMarshall(
        model=User, fields=["name", "email", "language", "description"]
    )
    extra_context: fields.MarshallField = fields.MarshallMethodField(field_type=dict[str, Any])

    def get_extra_context(self, instance) -> dict[str, Any]:
        return self.context


async def test_marshall_without_context():
    data = {
        "name": "Edgy",
        "email": "edgy@ravyn.dev",
        "language": "EN",
        "description": "A description",
    }

    user_marshalled = UserMarshall(**data)

    assert user_marshalled.model_dump() == {
        "name": "Edgy",
        "email": "edgy@ravyn.dev",
        "language": "EN",
        "description": "A description",
        "extra_context": {},
    }


async def test_marshall_with_empty_context():
    data = {
        "name": "Edgy",
        "email": "edgy@ravyn.dev",
        "language": "EN",
        "description": "A description",
    }

    user_marshalled = UserMarshall(**data, context={})

    assert user_marshalled.model_dump() == {
        "name": "Edgy",
        "email": "edgy@ravyn.dev",
        "language": "EN",
        "description": "A description",
        "extra_context": {},
    }


async def test_marshall_with_context():
    data = {
        "name": "Edgy",
        "email": "edgy@ravyn.dev",
        "language": "EN",
        "description": "A description",
    }

    user_marshalled = UserMarshall(**data, context={"foo": "bar"})

    assert user_marshalled.model_dump() == {
        "name": "Edgy",
        "email": "edgy@ravyn.dev",
        "language": "EN",
        "description": "A description",
        "extra_context": {"foo": "bar"},
    }
